"""
LLM 封装模块：基于 OpenAI 兼容 API 调用 LLM 生成 SQL 语句
"""
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# 自动加入系统路径
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import httpx
from openai import OpenAI
from app.config import settings
from app.schema_rag import schema_rag

SYSTEM_PROMPT = """你是一名资深的 SQLite 商业数据分析师与 SQL 专家。你的任务是根据给定的数据库 Schema 上下文和业务口径规范，将用户的自然语言问题转换为高效、准确、符合 SQLite 语法的 SQL 查询语句。

【严格遵从原则】：
1. 只能使用 SELECT 语句查询数据。禁止生成 INSERT/UPDATE/DELETE/DROP/ALTER/TRUNCATE 等修改操作。
2. 必须且只能使用上下文【相关的数据库 Schema】中明确给出的表和字段，切勿凭空编造表名或字段名。
3. 如果查询涉及到业务指标（如 GMV、客单价、毛利润），必须严格按照【业务指标口径规范】中给出的过滤条件与计算公式编写。
4. 【商业通用过滤约束】：凡是查询涉及订单表 `orders` 或订单明细表 `order_items`（无论是统计销量、销售额、购买用户还是明细列表），必须关联 `orders` 表并在 WHERE 子句中增加 `orders.pay_status = 'PAID'` 默认筛选！
5. 当使用 GROUP BY 语句时，SELECT 中未使用聚合函数的字段必须包含在 GROUP BY 子句中。
6. 输出要求：只输出可以直接运行的纯 SQL 代码（可以使用 ```sql 代码块包裹），严禁输出任何额外的分析过程、说明文字或对话聊天内容！

【少样本 (Few-shot) 示例参考】：

示例 1：
用户问题：至今已支付的总销售额 (GMV) 是多少？
输出 SQL：
```sql
SELECT SUM(total_amount) AS gmv FROM orders WHERE pay_status = 'PAID';
```

示例 2：
用户问题：销量最高的前 3 个商品及其对应的销售总量是多少？
输出 SQL：
```sql
SELECT p.product_name, SUM(oi.quantity) AS total_sold FROM order_items oi JOIN products p ON oi.product_id = p.product_id JOIN orders o ON oi.order_id = o.order_id WHERE o.pay_status = 'PAID' GROUP BY p.product_id, p.product_name ORDER BY total_sold DESC LIMIT 3;
```

示例 3：
用户问题：查询北京和上海的注册用户数量
输出 SQL：
```sql
SELECT city, COUNT(*) AS user_count FROM users WHERE city IN ('北京', '上海') GROUP BY city ORDER BY user_count DESC;
```
"""

def extract_sql_from_response(content: str) -> str:
    """
    从 LLM 返回的文本中清洗提取纯 SQL 语句
    支持提取 ```sql ... ``` 或 ``` ... ``` 代码块，并去除末尾多余分号与空白
    """
    if not content:
        return ""

    # 1. 尝试匹配 ```sql ... ``` 代码块
    sql_block_match = re.search(r"```sql\s*(.*?)\s*```", content, re.DOTALL | re.IGNORECASE)
    if sql_block_match:
        sql = sql_block_match.group(1).strip()
    else:
        # 2. 尝试匹配普通 ``` ... ``` 代码块
        generic_block_match = re.search(r"```\s*(.*?)\s*```", content, re.DOTALL)
        if generic_block_match:
            sql = generic_block_match.group(1).strip()
        else:
            # 3. 兜底：直接按行过滤说明性文字
            lines = content.strip().split("\n")
            sql_lines = [line for line in lines if not line.strip().startswith(("#", "//", "输出", "解释", "SQL:", "这里"))]
            sql = "\n".join(sql_lines).strip()

    # 清理行尾多余的分号与空白
    sql = re.sub(r";+\s*$", "", sql)
    return sql.strip()


class LLMClient:
    """OpenAI API 兼容大模型客户端"""

    def __init__(self):
        # 显式配置 trust_env=False 绕过系统代理干扰直连 API
        self.http_client = httpx.Client(trust_env=False, timeout=30.0)
        self.client = OpenAI(
            base_url=settings.LLM_BASE_URL,
            api_key=settings.LLM_API_KEY,
            http_client=self.http_client
        )
        self.model = settings.LLM_MODEL

    def generate_sql(
        self,
        question: str,
        schema_context: Optional[str] = None,
        temperature: float = 0.1
    ) -> Dict[str, Any]:
        """
        根据自然语言问题与 Schema 生成 SQL 语句

        :param question: 用户提出的分析问题
        :param schema_context: （可选）Schema 描述文本；若为 None 则自动调用 Schema RAG 检索生成
        :param temperature: 生成随机性，数据分析通常使用 0.1 较低值保证稳定性
        :return: {
            "sql": str,
            "raw_response": str,
            "schema_context": str,
            "usage": dict
        }
        """
        # 1. 若未传入 schema_context，则自动通过 Schema RAG 进行混合检索与 Context 裁剪
        if schema_context is None:
            schema_context = schema_rag.retrieve_and_prune_schema(question, top_k=settings.RAG_TOP_K)

        # 2. 组装 User Prompt
        user_prompt = f"""{schema_context}

### 【用户分析提问】:
{question}

请根据上面的 Schema 和约束，生成符合要求的 SQLite SQL 语句："""

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=1000
            )

            raw_content = response.choices[0].message.content.strip()
            clean_sql = extract_sql_from_response(raw_content)

            usage = {}
            if hasattr(response, "usage") and response.usage:
                usage = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }

            return {
                "success": True,
                "sql": clean_sql,
                "raw_response": raw_content,
                "schema_context": schema_context,
                "usage": usage,
                "error": None
            }

        except Exception as e:
            return {
                "success": False,
                "sql": "",
                "raw_response": "",
                "schema_context": schema_context,
                "usage": {},
                "error": f"LLM API Call Error: {str(e)}"
            }

llm_client = LLMClient()
