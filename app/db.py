"""
数据库连接与只读查询模块：安全的 SQLite 只读连接与结果格式化
"""
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple
from app.config import settings

def get_readonly_connection(db_path: Path = None) -> sqlite3.Connection:
    """
    获取 SQLite 只读数据库连接
    使用 URI 模式以 file:path?mode=ro 强行开启只读模式，拦截任何写事务
    """
    target_path = db_path or settings.abs_db_path
    if not target_path.exists():
        raise FileNotFoundError(f"数据库文件不存在: {target_path}")

    # SQLite URI 只读连接规范
    db_uri = f"file:{target_path.as_posix()}?mode=ro"
    conn = sqlite3.connect(db_uri, uri=True, check_same_thread=False)
    # 返回 dict 方式处理结果集
    conn.row_factory = sqlite3.Row
    return conn

def execute_readonly_query(
    sql: str,
    params: Tuple = (),
    max_rows: int = 1000,
    timeout_sec: float = 5.0
) -> Dict[str, Any]:
    """
    只读方式执行 SQL 查询

    :param sql: 待执行的 SQL 语句
    :param params: 参数绑定的元组
    :param max_rows: 返回的最大行数截断限制
    :param timeout_sec: 超时时间上限（秒）
    :return: {
        "success": bool,
        "columns": List[str],
        "rows": List[Dict[str, Any]],
        "row_count": int,
        "truncated": bool,
        "execution_time_ms": float,
        "error": str or None
    }
    """
    start_time = time.perf_counter()
    conn = None

    try:
        conn = get_readonly_connection()
        cursor = conn.cursor()

        # 执行 SQL
        cursor.execute(sql, params)
        
        # 获取列名
        columns = [description[0] for description in cursor.description] if cursor.description else []
        
        # 读取数据并进行行数限制防护
        raw_rows = cursor.fetchmany(max_rows + 1)
        truncated = len(raw_rows) > max_rows
        valid_rows = raw_rows[:max_rows]

        # 转换为列表字典
        rows = [dict(row) for row in valid_rows]
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        return {
            "success": True,
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "truncated": truncated,
            "execution_time_ms": round(elapsed_ms, 2),
            "error": None
        }

    except sqlite3.OperationalError as e:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        return {
            "success": False,
            "columns": [],
            "rows": [],
            "row_count": 0,
            "truncated": False,
            "execution_time_ms": round(elapsed_ms, 2),
            "error": f"Database Operational Error: {str(e)}"
        }
    except Exception as e:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        return {
            "success": False,
            "columns": [],
            "rows": [],
            "row_count": 0,
            "truncated": False,
            "execution_time_ms": round(elapsed_ms, 2),
            "error": f"Execution Error: {str(e)}"
        }
    finally:
        if conn:
            conn.close()
