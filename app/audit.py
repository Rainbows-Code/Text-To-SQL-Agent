"""
审计日志模块：记录全流程用户查询、生成的 SQL、耗时、结果行数及安全预警
导出日志到 data/audit_log.jsonl 文件
"""
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# 自动加入系统路径
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.config import settings

class AuditLogger:
    """全流程查询审计日志"""

    def __init__(self, log_path: Optional[Path] = None):
        self.log_path = log_path or (settings.abs_db_path.parent / "audit_log.jsonl")

    def log(
        self,
        question: str,
        raw_sql: str,
        sanitized_sql: str,
        is_safe: bool,
        execution_time_ms: float,
        row_count: int,
        success: bool,
        error: Optional[str] = None,
        user_id: str = "default_user",
        needs_confirmation: bool = False,
        risk_warnings: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """记录一条审计日志条目"""
        record = {
            "timestamp": datetime.now().isoformat(),
            "user_id": user_id,
            "question": question,
            "raw_sql": raw_sql,
            "sanitized_sql": sanitized_sql,
            "is_safe": is_safe,
            "execution_time_ms": round(execution_time_ms, 2),
            "row_count": row_count,
            "success": success,
            "error": error,
            "needs_confirmation": needs_confirmation,
            "risk_warnings": risk_warnings or []
        }

        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"[Audit Log Error] 写入日志失败: {e}")

        return record

    def get_recent_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """读取最近的审计日志记录"""
        if not self.log_path.exists():
            return []

        logs = []
        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        logs.append(json.loads(line))
        except Exception as e:
            print(f"[Audit Read Error] 读取日志失败: {e}")

        return logs[-limit:]

audit_logger = AuditLogger()
