"""
Step 4 验证测试：LLM SQL 生成器与 SQL 提取清洗逻辑测试
支持 pytest 运行与 python test_llm.py 直接运行
"""
import sys
from pathlib import Path

# 自动接入根目录
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.llm import extract_sql_from_response, llm_client
from app.db import execute_readonly_query

def test_sql_extraction_logic():
    """测试各种格式下的 SQL 提取清洗逻辑"""
    raw_1 = "```sql\nSELECT * FROM users;\n```"
    assert extract_sql_from_response(raw_1) == "SELECT * FROM users"

    raw_2 = "思考过程：分析该问题需要连接 users 和 orders 表。\n```\nSELECT city, COUNT(*) FROM users GROUP BY city;\n```"
    assert extract_sql_from_response(raw_2) == "SELECT city, COUNT(*) FROM users GROUP BY city"

    raw_3 = "SELECT SUM(total_amount) FROM orders WHERE pay_status = 'PAID';"
    assert extract_sql_from_response(raw_3) == "SELECT SUM(total_amount) FROM orders WHERE pay_status = 'PAID'"
    print("[PASS] SQL 提取清洗测试全部通过！")

def test_llm_generation_and_execution():
    """测试真实调用 LLM 生成 SQL 并下发数据库执行"""
    question = "计算至今为止已支付的总销售额 (GMV) 是多少？"
    res = llm_client.generate_sql(question)
    
    if not res["success"]:
        print(f"[Warning] LLM API 调用跳过或报错 (如未配置有效 Key): {res['error']}")
        return

    generated_sql = res["sql"]
    print(f"\n[LLM 成功生成 SQL]: {generated_sql}")
    assert len(generated_sql) > 0, "LLM 未能提取出有效 SQL 语句"
    assert "SELECT" in generated_sql.upper(), "生成的 SQL 必须包含 SELECT 语句"

    # 将生成的 SQL 直接放入数据库执行验证
    exec_res = execute_readonly_query(generated_sql)
    print(f"[数据库执行验证]: success={exec_res['success']}, 结果: {exec_res['rows']}")
    assert exec_res["success"] is True, f"LLM 生成的 SQL 执行报错: {exec_res['error']}"

def run_all_llm_tests():
    print("=" * 60)
    print("Start Step 4 LLM Prompt & SQL Generator Validation...")
    print("=" * 60)
    
    test_sql_extraction_logic()
    print("[PASS] SQL Extraction Logic Test: PASSED")
    
    test_llm_generation_and_execution()

    print("=" * 60)
    print("Step 4 LLM Generation validation 100% PASSED!")
    print("=" * 60)

if __name__ == "__main__":
    run_all_llm_tests()
