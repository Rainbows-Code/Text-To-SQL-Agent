"""
Text-to-SQL 数据分析 Agent 核心控制层
实现 “生成 -> AST校验 -> 数据库只读执行 -> 自自我修复 (最多3轮) -> 审计日志” 的完整闭环
"""
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# 自动加入系统路径
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.config import settings
from app.db import execute_readonly_query
from app.schema_rag import schema_rag
from app.llm import llm_client, extract_sql_from_response
from app.sql_guard import sql_guard
from app.audit import audit_logger

REPAIR_SYSTEM_PROMPT = """你是一名擅长 SQLite 调试与修复的资深 SQL 专家。
上一轮生成的 SQL 语句在数据库实际执行时抛出了报错。请仔细分析数据库返回的 Traceback 报错提示，识别错误原因（如字段名错误、表名误用、GROUP BY 缺字段、JOIN 条件错误等），并修正生成正确可直接执行的 SQLite SQL 语句。

【严格限制】：只输出修改后的纯 SQL 语句（可放在 ```sql 代码块中），不要输出任何解释或说明性文字。"""

class Text2SQLAgent:
    """Text-to-SQL 数据分析闭环 Agent"""

    def __init__(self, max_repair_turns: int = None):
        self.max_repair_turns = max_repair_turns or settings.MAX_REPAIR_TURNS

    def run_query(
        self,
        question: str,
        user_id: str = "default_user",
        force_schema_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        运行用户查询的主入口（闭环控制器）

        :param question: 用户自然语言提问
        :param user_id: 用户唯一标识
        :param force_schema_context: （可选）强制指定 Schema，不指定则自动调用 RAG
        :return: {
            "success": bool,
            "question": str,
            "final_sql": str,
            "columns": List[str],
            "rows": List[Dict],
            "row_count": int,
            "execution_time_ms": float,
            "total_turns": int,
            "repair_history": List[Dict],
            "human_handoff": bool,
            "needs_confirmation": bool,
            "risk_warnings": List[str],
            "error": str or None,
            "explanation": str
        }
        """
        start_time = time.perf_counter()
        
        # 1. Schema RAG 混合检索与动态 Context 裁剪
        schema_context = force_schema_context or schema_rag.retrieve_and_prune_schema(question, top_k=settings.RAG_TOP_K)

        repair_history: List[Dict[str, Any]] = []
        current_sql = ""
        last_error = None
        human_handoff = False
        needs_confirmation = False
        risk_warnings = []

        total_prompt_tokens = 0
        total_completion_tokens = 0

        # 闭环循环（最多 3 轮：初次生成 + 2 轮修复）
        for turn in range(1, self.max_repair_turns + 1):
            turn_start_time = time.perf_counter()

            # A. 生成阶段 (Generate / Repair)
            if turn == 1:
                # 第一轮：标准生成
                llm_res = llm_client.generate_sql(question, schema_context=schema_context)
                if llm_res.get("usage"):
                    total_prompt_tokens += llm_res["usage"].get("prompt_tokens", 0)
                    total_completion_tokens += llm_res["usage"].get("completion_tokens", 0)
            else:
                # 修复轮：构造带报错 Traceback 的修补 Prompt
                repair_prompt = f"""### 【用户提问】:
{question}

{schema_context}

### 【上一轮尝试的 SQL】:
```sql
{current_sql}
```

### 【数据库报错信息 (Error Traceback)】:
{last_error}

请仔细分析报错，纠正 SQL 语法或字段匹配错误，输出修复后的 SQLite SQL 语句："""

                # 调用 LLM 进行针对性修补
                messages = [
                    {"role": "system", "content": REPAIR_SYSTEM_PROMPT},
                    {"role": "user", "content": repair_prompt}
                ]
                try:
                    response = llm_client.client.chat.completions.create(
                        model=llm_client.model,
                        messages=messages,
                        temperature=0.1
                    )
                    raw_content = response.choices[0].message.content.strip()
                    clean_sql = extract_sql_from_response(raw_content)
                    if hasattr(response, "usage") and response.usage:
                        total_prompt_tokens += getattr(response.usage, "prompt_tokens", 0) or 0
                        total_completion_tokens += getattr(response.usage, "completion_tokens", 0) or 0

                    llm_res = {
                        "success": True,
                        "sql": clean_sql,
                        "raw_response": raw_content,
                        "error": None
                    }
                except Exception as e:
                    llm_res = {
                        "success": False,
                        "sql": "",
                        "raw_response": "",
                        "error": f"LLM Repair Call Failed: {str(e)}"
                    }

            if not llm_res["success"]:
                last_error = llm_res["error"]
                repair_history.append({
                    "turn": turn,
                    "sql": "",
                    "success": False,
                    "stage": "LLM_GENERATE",
                    "error": last_error
                })
                continue

            current_sql = llm_res["sql"]

            # B. 验证阶段 (SQL AST Safety Guard)
            guard_res = sql_guard.validate_and_sanitize(current_sql)
            if not guard_res["is_safe"]:
                last_error = f"SQL AST Guard Refused: {guard_res['reason']}"
                repair_history.append({
                    "turn": turn,
                    "sql": current_sql,
                    "success": False,
                    "stage": "SQL_GUARD",
                    "error": last_error
                })
                # 如果是恶意写 SQL 拦截，直接跳出或进入修复
                continue

            sanitized_sql = guard_res["sanitized_sql"]
            needs_confirmation = guard_res["needs_confirmation"]
            risk_warnings = guard_res["risk_warnings"]

            # C. 执行阶段 (Database ReadOnly Execution)
            exec_res = execute_readonly_query(sanitized_sql)
            turn_elapsed_ms = (time.perf_counter() - turn_start_time) * 1000

            if exec_res["success"]:
                # 唯一事实来源：数据库只读执行成功！
                total_elapsed_ms = (time.perf_counter() - start_time) * 1000
                
                repair_history.append({
                    "turn": turn,
                    "sql": sanitized_sql,
                    "success": True,
                    "stage": "EXECUTE",
                    "execution_time_ms": exec_res["execution_time_ms"],
                    "row_count": exec_res["row_count"],
                    "error": None
                })

                # 记录审计日志
                audit_logger.log(
                    question=question,
                    raw_sql=current_sql,
                    sanitized_sql=sanitized_sql,
                    is_safe=True,
                    execution_time_ms=total_elapsed_ms,
                    row_count=exec_res["row_count"],
                    success=True,
                    user_id=user_id,
                    needs_confirmation=needs_confirmation,
                    risk_warnings=risk_warnings
                )

                explanation = self._generate_simple_explanation(question, exec_res["row_count"], turn)

                turn1_sql = repair_history[0]["sql"] if repair_history else sanitized_sql

                return {
                    "success": True,
                    "question": question,
                    "turn1_sql": turn1_sql,
                    "final_sql": sanitized_sql,
                    "columns": exec_res["columns"],
                    "rows": exec_res["rows"],
                    "row_count": exec_res["row_count"],
                    "execution_time_ms": round(total_elapsed_ms, 2),
                    "total_turns": turn,
                    "repair_history": repair_history,
                    "human_handoff": False,
                    "needs_confirmation": needs_confirmation,
                    "risk_warnings": risk_warnings,
                    "total_prompt_tokens": total_prompt_tokens,
                    "total_completion_tokens": total_completion_tokens,
                    "total_tokens": total_prompt_tokens + total_completion_tokens,
                    "error": None,
                    "explanation": explanation
                }

            else:
                # 数据库报错，记录错误并触发下一轮自自我修复
                last_error = exec_res["error"]
                repair_history.append({
                    "turn": turn,
                    "sql": sanitized_sql,
                    "success": False,
                    "stage": "EXECUTE",
                    "execution_time_ms": exec_res["execution_time_ms"],
                    "error": last_error
                })

        # 3. 超过 3 轮修复依然失败 -> 转人工介入 (Human Handoff)
        total_elapsed_ms = (time.perf_counter() - start_time) * 1000
        human_handoff = True

        audit_logger.log(
            question=question,
            raw_sql=current_sql,
            sanitized_sql=current_sql,
            is_safe=False,
            execution_time_ms=total_elapsed_ms,
            row_count=0,
            success=False,
            error=f"Exceeded {self.max_repair_turns} repair turns. Escalate to human handoff.",
            user_id=user_id
        )

        turn1_sql = repair_history[0]["sql"] if repair_history else current_sql

        return {
            "success": False,
            "question": question,
            "turn1_sql": turn1_sql,
            "final_sql": current_sql,
            "columns": [],
            "rows": [],
            "row_count": 0,
            "execution_time_ms": round(total_elapsed_ms, 2),
            "total_turns": self.max_repair_turns,
            "repair_history": repair_history,
            "human_handoff": True,
            "needs_confirmation": False,
            "risk_warnings": risk_warnings,
            "total_prompt_tokens": total_prompt_tokens,
            "total_completion_tokens": total_completion_tokens,
            "total_tokens": total_prompt_tokens + total_completion_tokens,
            "error": f"经过 {self.max_repair_turns} 轮尝试自动修正后仍无法正确执行，错误: {last_error}",
            "explanation": "系统多次尝试修复 SQL 依然失败，已自动触发【转人工介入 (Human Handoff)】流程。"
        }

    def _generate_simple_explanation(self, question: str, row_count: int, turns: int) -> str:
        """生成简要的结果描述"""
        if turns == 1:
            return f"成功一次性生成并执行 SQL，共检索到 {row_count} 条分析数据。"
        else:
            return f"经过 {turns} 轮自动反馈修复后成功修正并执行 SQL，共检索到 {row_count} 条分析数据。"

agent = Text2SQLAgent()
