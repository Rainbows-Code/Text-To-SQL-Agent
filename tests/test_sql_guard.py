"""
Step 5 验证测试：SQL AST 安全校验防护层与审计日志测试
支持 pytest 运行与 python test_sql_guard.py 直接运行
"""
import sys
from pathlib import Path

# 自动接入系统路径
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.sql_guard import sql_guard
from app.audit import audit_logger

def test_legal_select_passthrough():
    """测试合法的 SELECT 语句允许通过"""
    sql = "SELECT user_name, city FROM users WHERE age > 30 LIMIT 10;"
    res = sql_guard.validate_and_sanitize(sql)
    assert res["is_safe"] is True
    assert res["sanitized_sql"] == "SELECT user_name, city FROM users WHERE age > 30 LIMIT 10"
    print("[PASS] 合法 SELECT 语句校验通过！")

def test_auto_limit_injection():
    """测试缺失 LIMIT 的 SELECT 语句被自动注入 LIMIT 100 保底截断"""
    sql = "SELECT city, COUNT(*) FROM users GROUP BY city"
    res = sql_guard.validate_and_sanitize(sql)
    assert res["is_safe"] is True
    assert "LIMIT 100" in res["sanitized_sql"].upper(), f"未补全 LIMIT，结果为: {res['sanitized_sql']}"
    print(f"[PASS] 缺失 LIMIT 语句自动注入成功: {res['sanitized_sql']}")

def test_malicious_dml_ddl_interception():
    """测试非法 DML/DDL (DELETE, DROP, UPDATE, INSERT) 被强行拦截"""
    malicious_sqls = [
        ("DELETE FROM users WHERE user_id = 1", "DELETE"),
        ("DROP TABLE orders", "DROP"),
        ("UPDATE products SET price = 0", "UPDATE"),
        ("INSERT INTO users VALUES (99, '黑客', '男', 20, '北京', '2026-01-01')", "INSERT"),
        ("ALTER TABLE users DROP COLUMN city", "ALTER"),
    ]

    for sql, kw in malicious_sqls:
        res = sql_guard.validate_and_sanitize(sql)
        assert res["is_safe"] is False, f"非法 SQL [{sql}] 未被拦截！"
        assert res["reason"] is not None
        print(f"[PASS] Malicious SQL blocked: [{sql}] -> Reason: {res['reason']}")

def test_multi_statement_injection_interception():
    """测试分号拼接多语句注入攻击被强行拦截"""
    sql = "SELECT * FROM users; DROP TABLE orders;"
    res = sql_guard.validate_and_sanitize(sql)
    assert res["is_safe"] is False
    assert "禁止拼接多条" in res["reason"]
    print(f"[PASS] 多语句拼接注入成功拦截！理由: {res['reason']}")

def test_high_risk_query_warning():
    """测试大表缺失 WHERE 条件触发二次确认标识"""
    sql = "SELECT * FROM orders;"
    res = sql_guard.validate_and_sanitize(sql)
    assert res["is_safe"] is True
    assert res["needs_confirmation"] is True
    assert len(res["risk_warnings"]) > 0
    print(f"[PASS] 大表无 WHERE 条件高风险提示触发成功: {res['risk_warnings']}")

def test_audit_logging():
    """测试审计日志全流程记录与读取"""
    record = audit_logger.log(
        question="测试查询",
        raw_sql="SELECT * FROM users",
        sanitized_sql="SELECT * FROM users LIMIT 100",
        is_safe=True,
        execution_time_ms=5.2,
        row_count=8,
        success=True
    )
    assert record["user_id"] == "default_user"
    assert record["row_count"] == 8

    logs = audit_logger.get_recent_logs(limit=5)
    assert len(logs) > 0
    print(f"[PASS] 审计日志写入与读取测试通过！最新日志条目数: {len(logs)}")

def run_all_sql_guard_tests():
    print("=" * 60)
    print("Start Step 5 SQL Guard & Audit Validation...")
    print("=" * 60)
    
    test_legal_select_passthrough()
    test_auto_limit_injection()
    test_malicious_dml_ddl_interception()
    test_multi_statement_injection_interception()
    test_high_risk_query_warning()
    test_audit_logging()

    print("=" * 60)
    print("Step 5 SQL Guard & Audit validation 100% PASSED!")
    print("=" * 60)

if __name__ == "__main__":
    run_all_sql_guard_tests()
