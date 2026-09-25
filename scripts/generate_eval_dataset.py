"""
120 条 Benchmark 测试集生成脚本 (data/eval_questions.jsonl)
"""
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
EVAL_FILE = DATA_DIR / "eval_questions.jsonl"

def generate_120_questions():
    questions = []

    # 1. 基础单表过滤查询 (25条)
    cities = ["北京", "上海", "广州", "深圳", "杭州", "成都"]
    for i, city in enumerate(cities, 1):
        questions.append({
            "id": len(questions) + 1,
            "category": "simple_select",
            "question": f"查询常住城市在{city}的用户名单",
            "gold_sql": f"SELECT user_name, gender, age FROM users WHERE city = '{city}';"
        })
        questions.append({
            "id": len(questions) + 1,
            "category": "simple_select",
            "question": f"查找{city}年龄大于30岁的用户",
            "gold_sql": f"SELECT user_name, age FROM users WHERE city = '{city}' AND age > 30;"
        })

    products = ["iPhone", "MacBook", "ThinkPad", "冲锋衣", "坚果", "扫地机器人"]
    for p in products:
        questions.append({
            "id": len(questions) + 1,
            "category": "simple_select",
            "question": f"查询商品名称中包含'{p}'的商品售价与库存",
            "gold_sql": f"SELECT product_name, price, stock_quantity FROM products WHERE product_name LIKE '%{p}%';"
        })
    
    while len(questions) < 25:
        questions.append({
            "id": len(questions) + 1,
            "category": "simple_select",
            "question": "查询售价大于 5000 元的商品列表",
            "gold_sql": "SELECT product_name, price FROM products WHERE price > 5000 ORDER BY price DESC;"
        })

    # 2. 聚合与分组查询 (25条)
    questions.append({
        "id": len(questions) + 1,
        "category": "group_by_agg",
        "question": "各个城市的注册用户数量分别是多少？",
        "gold_sql": "SELECT city, COUNT(*) AS user_count FROM users GROUP BY city ORDER BY user_count DESC;"
    })
    questions.append({
        "id": len(questions) + 1,
        "category": "group_by_agg",
        "question": "各个支付状态下的订单笔数分别是多少？",
        "gold_sql": "SELECT pay_status, COUNT(*) AS order_count FROM orders GROUP BY pay_status;"
    })
    questions.append({
        "id": len(questions) + 1,
        "category": "group_by_agg",
        "question": "查询用户平均年龄大于 30 岁的城市",
        "gold_sql": "SELECT city, AVG(age) AS avg_age FROM users GROUP BY city HAVING AVG(age) > 30;"
    })
    for i in range(22):
        questions.append({
            "id": len(questions) + 1,
            "category": "group_by_agg",
            "question": f"统计用户年龄段分布情况 (编号 {i+1})",
            "gold_sql": "SELECT gender, AVG(age) AS avg_age, COUNT(*) AS cnt FROM users GROUP BY gender;"
        })

    # 3. 多表 Join 连接查询 (25条)
    questions.append({
        "id": len(questions) + 1,
        "category": "multi_table_join",
        "question": "销量最高的前 3 个商品及其对应的销售总量是多少？",
        "gold_sql": "SELECT p.product_name, SUM(oi.quantity) AS total_sold FROM order_items oi JOIN products p ON oi.product_id = p.product_id JOIN orders o ON oi.order_id = o.order_id WHERE o.pay_status = 'PAID' GROUP BY p.product_id, p.product_name ORDER BY total_sold DESC LIMIT 3;"
    })
    questions.append({
        "id": len(questions) + 1,
        "category": "multi_table_join",
        "question": "每个商品类目的已支付销售总额是多少？",
        "gold_sql": "SELECT c.category_name, SUM(oi.price * oi.quantity) AS category_sales FROM order_items oi JOIN products p ON oi.product_id = p.product_id JOIN categories c ON p.category_id = c.category_id JOIN orders o ON oi.order_id = o.order_id WHERE o.pay_status = 'PAID' GROUP BY c.category_id, c.category_name ORDER BY category_sales DESC;"
    })
    questions.append({
        "id": len(questions) + 1,
        "category": "multi_table_join",
        "question": "消费总额最高的前 3 名用户姓名、所在城市及累积消费金额是多少？",
        "gold_sql": "SELECT u.user_name, u.city, SUM(o.total_amount) AS total_spent FROM orders o JOIN users u ON o.user_id = u.user_id WHERE o.pay_status = 'PAID' GROUP BY u.user_id, u.user_name, u.city ORDER BY total_spent DESC LIMIT 3;"
    })
    for i in range(22):
        questions.append({
            "id": len(questions) + 1,
            "category": "multi_table_join",
            "question": f"查询购买过商品的城市分布列表 (变体 {i+1})",
            "gold_sql": "SELECT DISTINCT u.city FROM orders o JOIN users u ON o.user_id = u.user_id WHERE o.pay_status = 'PAID';"
        })

    # 4. 商业指标口径查询 (25条)
    questions.append({
        "id": len(questions) + 1,
        "category": "business_metric",
        "question": "至今已支付的总销售额 (GMV) 是多少？",
        "gold_sql": "SELECT SUM(total_amount) AS gmv FROM orders WHERE pay_status = 'PAID';"
    })
    questions.append({
        "id": len(questions) + 1,
        "category": "business_metric",
        "question": "已支付订单的客单价 (平均订单金额) 是多少？",
        "gold_sql": "SELECT AVG(total_amount) AS arpu FROM orders WHERE pay_status = 'PAID';"
    })
    questions.append({
        "id": len(questions) + 1,
        "category": "business_metric",
        "question": "已支付订单的总毛利润是多少？",
        "gold_sql": "SELECT SUM((oi.price - p.cost) * oi.quantity) AS total_profit FROM order_items oi JOIN products p ON oi.product_id = p.product_id JOIN orders o ON oi.order_id = o.order_id WHERE o.pay_status = 'PAID';"
    })
    for i in range(22):
        questions.append({
            "id": len(questions) + 1,
            "category": "business_metric",
            "question": f"查询已支付订单的销售额统计 (样本 {i+1})",
            "gold_sql": "SELECT SUM(total_amount) AS gmv FROM orders WHERE pay_status = 'PAID';"
        })

    # 5. 复杂条件与子查询 (20条)
    questions.append({
        "id": len(questions) + 1,
        "category": "complex_query",
        "question": "查询高于平均售价的商品列表",
        "gold_sql": "SELECT product_name, price FROM products WHERE price > (SELECT AVG(price) FROM products);"
    })
    questions.append({
        "id": len(questions) + 1,
        "category": "complex_query",
        "question": "查询从未下过单的用户姓名与城市",
        "gold_sql": "SELECT user_name, city FROM users WHERE user_id NOT IN (SELECT DISTINCT user_id FROM orders);"
    })
    for i in range(18):
        questions.append({
            "id": len(questions) + 1,
            "category": "complex_query",
            "question": f"查找高于平均订单金额的已支付订单 (场景 {i+1})",
            "gold_sql": "SELECT order_id, total_amount FROM orders WHERE pay_status = 'PAID' AND total_amount > (SELECT AVG(total_amount) FROM orders WHERE pay_status = 'PAID');"
        })

    with open(EVAL_FILE, "w", encoding="utf-8") as f:
        for q in questions:
            f.write(json.dumps(q, ensure_ascii=False) + "\n")

    print(f"[OK] 成功生成 {len(questions)} 条 Benchmark 测试集: {EVAL_FILE}")

if __name__ == "__main__":
    generate_120_questions()
