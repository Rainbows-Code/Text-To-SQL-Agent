"""
Step 2 验证测试：测试 5 条核心业务问题与其 Gold SQL 的只读查询执行
支持 pytest 运行与 python test_step2.py 直接运行
"""
import sys
from pathlib import Path

# 自动将项目根目录添加到 python path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.db import execute_readonly_query
from app.schema import schema_manager

TEST_CASE_QUESTIONS = [
    {
        "id": 1,
        "question": "至今已支付的总销售额 (GMV) 是多少？",
        "gold_sql": "SELECT SUM(total_amount) AS gmv FROM orders WHERE pay_status = 'PAID';"
    },
    {
        "id": 2,
        "question": "各个城市的注册用户数量分别是多少？",
        "gold_sql": "SELECT city, COUNT(*) AS user_count FROM users GROUP BY city ORDER BY user_count DESC;"
    },
    {
        "id": 3,
        "question": "销量最高的前 3 个商品及其对应的销售总量是多少？",
        "gold_sql": """
        SELECT p.product_name, SUM(oi.quantity) AS total_sold
        FROM order_items oi
        JOIN products p ON oi.product_id = p.product_id
        JOIN orders o ON oi.order_id = o.order_id
        WHERE o.pay_status = 'PAID'
        GROUP BY p.product_id, p.product_name
        ORDER BY total_sold DESC LIMIT 3;
        """
    },
    {
        "id": 4,
        "question": "每个商品类目的已支付销售总额是多少？",
        "gold_sql": """
        SELECT c.category_name, SUM(oi.price * oi.quantity) AS category_sales
        FROM order_items oi
        JOIN products p ON oi.product_id = p.product_id
        JOIN categories c ON p.category_id = c.category_id
        JOIN orders o ON oi.order_id = o.order_id
        WHERE o.pay_status = 'PAID'
        GROUP BY c.category_id, c.category_name
        ORDER BY category_sales DESC;
        """
    },
    {
        "id": 5,
        "question": "消费总额最高的前 3 名用户姓名、所在城市及累积消费金额是多少？",
        "gold_sql": """
        SELECT u.user_name, u.city, SUM(o.total_amount) AS total_spent
        FROM orders o
        JOIN users u ON o.user_id = u.user_id
        WHERE o.pay_status = 'PAID'
        GROUP BY u.user_id, u.user_name, u.city
        ORDER BY total_spent DESC LIMIT 3;
        """
    }
]

def test_schema_loading():
    tables = schema_manager.get_tables()
    assert len(tables) == 5, f"预期 5 张表，实际读取到 {len(tables)} 张"
    metrics = schema_manager.get_metrics()
    assert len(metrics) >= 3, "预期至少 3 条业务指标口径"

def run_all_manual_tests():
    print("=" * 60)
    print("Start Step 2 Database & Schema Validation...")
    print("=" * 60)
    test_schema_loading()
    print("[PASS] Schema Metadata and Table Loading: PASSED")

    for case in TEST_CASE_QUESTIONS:
        res = execute_readonly_query(case["gold_sql"])
        assert res["success"] is True, f"Failed: {res['error']}"
        assert res["row_count"] > 0, "Row count is 0"
        print(f"\n[PASS] Question {case['id']}: {case['question']}")
        print(f"       Gold SQL: {case['gold_sql'].strip()}")
        print(f"       Result ({res['execution_time_ms']}ms): {res['rows']}")

    print("\n" + "=" * 60)
    print("Step 2 all 6 database & SQL tests 100% PASSED!")
    print("=" * 60)

if __name__ == "__main__":
    run_all_manual_tests()
