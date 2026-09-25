"""
FastAPI 主入口模块：提供数据分析 Agent RESTful API 接口服务
"""
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# 自动加入系统路径
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.config import settings
from app.db import execute_readonly_query
from app.agent import agent
from app.audit import audit_logger

app = FastAPI(
    title="Text-to-SQL 数据分析 Agent API",
    description="提供基于 Schema RAG、SQL AST 安全防护与自修复闭环的数据分析 Agent 后端服务",
    version="1.0.0"
)

# 允许跨域请求 (CORS Middleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 定义请求与响应数据模型 (Pydantic Models)
class QueryRequest(BaseModel):
    question: str = Field(..., description="用户提出的自然语言商业数据分析问题", example="至今已支付的总销售额 (GMV) 是多少？")
    user_id: str = Field("default_user", description="用户唯一标识")


class QueryResponse(BaseModel):
    success: bool = Field(..., description="是否成功执行查询")
    question: str = Field(..., description="原始提问")
    final_sql: str = Field(..., description="最终确定的 SQL 语句")
    columns: List[str] = Field(default_factory=list, description="结果表列名")
    rows: List[Dict[str, Any]] = Field(default_factory=list, description="结果集列表")
    row_count: int = Field(0, description="结果总行数")
    execution_time_ms: float = Field(0.0, description="端到端总耗时 (毫秒)")
    total_turns: int = Field(1, description="消耗的修复/生成轮次数")
    human_handoff: bool = Field(False, description="是否触发转人工介入流程")
    needs_confirmation: bool = Field(False, description="是否触发高风险查询二次确认预警")
    risk_warnings: List[str] = Field(default_factory=list, description="高风险安全预警提示信息")
    error: Optional[str] = Field(None, description="错误 Traceback 或失败信息")
    explanation: str = Field("", description="自然语言结果摘要说明")


@app.get("/health", summary="系统健康检查与数据库连通性诊断", tags=["系统管理"])
def health_check():
    """验证 REST API 状态与 SQLite 只读数据库可用性"""
    db_exists = settings.abs_db_path.exists()
    db_status = "connected"
    
    if db_exists:
        res = execute_readonly_query("SELECT 1 AS test;")
        if not res["success"]:
            db_status = f"error: {res['error']}"
    else:
        db_status = "database_file_not_found"

    return {
        "status": "ok",
        "database": db_status,
        "database_path": str(settings.abs_db_path),
        "llm_model": settings.LLM_MODEL,
        "version": "1.0.0"
    }


@app.post("/query", response_model=QueryResponse, summary="Text-to-SQL 分析查询主接口", tags=["Agent 分析"])
def process_query(request: QueryRequest):
    """
    接收用户提问，触发 Schema RAG + SQL Guard + 自自我修复闭环 Agent 进行数据分析
    """
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="提问内容不能为空")

    try:
        agent_result = agent.run_query(
            question=request.question,
            user_id=request.user_id
        )
        return QueryResponse(**agent_result)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent 执行内部异常: {str(e)}")


@app.get("/audit", summary="查看全流程审计日志记录", tags=["审计日志"])
def get_audit_logs(limit: int = Query(50, ge=1, le=200, description="返回的最大日志行数")):
    """获取最近的审计日志清单"""
    logs = audit_logger.get_recent_logs(limit=limit)
    return {
        "total_records": len(logs),
        "logs": logs
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
