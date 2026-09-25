"""
数据库初始化脚本：创建 SQLite 电商分析数据库 (data/database.sqlite) 并填充示例数据
"""
import os
import sqlite3
from pathlib import Path

# 获取数据库目标路径
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "database.sqlite"

def init_database():
    if DB_PATH.exists():
        os.remove(DB_PATH)
        print(f"清空旧数据库: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. 建表 DDL
    cursor.executescript("""
    -- 类目表
    CREATE TABLE categories (
        category_id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_name VARCHAR(50) NOT NULL,
        parent_id INTEGER NULL,
        FOREIGN KEY (parent_id) REFERENCES categories(category_id)
    );

    -- 商品表
    CREATE TABLE products (
        product_id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_name VARCHAR(100) NOT NULL,
        category_id INTEGER NOT NULL,
        price DECIMAL(10, 2) NOT NULL,
        cost DECIMAL(10, 2) NOT NULL,
        stock_quantity INTEGER NOT NULL DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (category_id) REFERENCES categories(category_id)
    );

    -- 用户表
    CREATE TABLE users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_name VARCHAR(50) NOT NULL,
        gender VARCHAR(10) CHECK(gender IN ('男', '女')),
        age INTEGER CHECK(age > 0),
        city VARCHAR(50) NOT NULL,
        registered_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    -- 订单表
    CREATE TABLE orders (
        order_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        total_amount DECIMAL(10, 2) NOT NULL,
        pay_status VARCHAR(20) NOT NULL CHECK(pay_status IN ('PAID', 'PENDING', 'CANCELLED', 'REFUNDED')),
        created_at DATETIME NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    );

    -- 订单明细表
    CREATE TABLE order_items (
        item_id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL CHECK(quantity > 0),
        price DECIMAL(10, 2) NOT NULL,
        FOREIGN KEY (order_id) REFERENCES orders(order_id),
        FOREIGN KEY (product_id) REFERENCES products(product_id)
    );
    """)

    # 2. 插入测试数据 DML
    # (1) 类目数据
    categories_data = [
        (1, '数码电子', None),
        (2, '服装鞋帽', None),
        (3, '食品饮料', None),
        (4, '家居用品', None),
        (5, '手机通讯', 1),
        (6, '电脑办公', 1),
        (7, '潮流男装', 2),
        (8, '休闲女装', 2),
        (9, '休闲零食', 3),
        (10, '智能家电', 4)
    ]
    cursor.executemany("INSERT INTO categories VALUES (?, ?, ?);", categories_data)

    # (2) 商品数据
    products_data = [
        (1, 'iPhone 16 Pro 256G', 5, 8999.00, 6800.00, 50, '2025-09-01 10:00:00'),
        (2, '小米15 16GB+512GB', 5, 4499.00, 3200.00, 100, '2025-10-15 10:00:00'),
        (3, 'MacBook Air M3 16G', 6, 9499.00, 7200.00, 30, '2025-08-10 10:00:00'),
        (4, '联想 ThinkPad X1 Carbon', 6, 10999.00, 8500.00, 20, '2025-07-20 10:00:00'),
        (5, '三防保暖冲锋衣 男款', 7, 599.00, 220.00, 200, '2025-11-01 10:00:00'),
        (6, '优衣库 纯棉针织衫 女款', 8, 199.00, 60.00, 300, '2025-11-05 10:00:00'),
        (7, '三只松鼠 坚果大礼包 1.5kg', 9, 129.00, 55.00, 500, '2025-12-01 10:00:00'),
        (8, '阿拉比卡 烘焙咖啡豆 500g', 9, 88.00, 35.00, 400, '2025-12-05 10:00:00'),
        (9, '石头 扫地机器人 G20S', 10, 3999.00, 2600.00, 40, '2025-10-01 10:00:00'),
        (10, '人体工学网椅 办公椅', 10, 899.00, 380.00, 80, '2025-09-15 10:00:00')
    ]
    cursor.executemany("INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?);", products_data)

    # (3) 用户数据
    users_data = [
        (1, '张伟', '男', 28, '北京', '2025-01-15 14:20:00'),
        (2, '王芳', '女', 32, '上海', '2025-02-20 09:15:00'),
        (3, '李强', '男', 45, '深圳', '2025-03-10 16:45:00'),
        (4, '刘洋', '女', 24, '广州', '2025-04-05 11:30:00'),
        (5, '陈杰', '男', 35, '杭州', '2025-05-12 18:10:00'),
        (6, '杨静', '女', 29, '北京', '2025-06-18 20:05:00'),
        (7, '赵磊', '男', 31, '上海', '2025-07-22 13:50:00'),
        (8, '孙梅', '女', 38, '成都', '2025-08-30 15:25:00')
    ]
    cursor.executemany("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?);", users_data)

    # (4) 订单数据
    orders_data = [
        (1, 1, 8999.00, 'PAID', '2026-01-10 10:15:00'),
        (2, 2, 9499.00, 'PAID', '2026-01-12 14:30:00'),
        (3, 3, 10999.00, 'PAID', '2026-01-15 09:20:00'),
        (4, 4, 398.00, 'PAID', '2026-01-18 16:40:00'),
        (5, 5, 4499.00, 'PAID', '2026-01-20 11:10:00'),
        (6, 6, 129.00, 'PAID', '2026-02-01 19:00:00'),
        (7, 1, 3999.00, 'PAID', '2026-02-05 15:30:00'),
        (8, 7, 599.00, 'CANCELLED', '2026-02-08 12:00:00'),
        (9, 8, 899.00, 'PAID', '2026-02-10 10:00:00'),
        (10, 2, 88.00, 'REFUNDED', '2026-02-14 18:20:00'),
        (11, 3, 8999.00, 'PAID', '2026-02-20 14:00:00'),
        (12, 5, 258.00, 'PAID', '2026-02-25 17:15:00')
    ]
    cursor.executemany("INSERT INTO orders VALUES (?, ?, ?, ?, ?);", orders_data)

    # (5) 订单明细数据
    order_items_data = [
        (1, 1, 1, 1, 8999.00),
        (2, 2, 3, 1, 9499.00),
        (3, 3, 4, 1, 10999.00),
        (4, 4, 6, 2, 199.00),
        (5, 5, 2, 1, 4499.00),
        (6, 6, 7, 1, 129.00),
        (7, 7, 9, 1, 3999.00),
        (8, 8, 5, 1, 599.00),
        (9, 9, 10, 1, 899.00),
        (10, 10, 8, 1, 88.00),
        (11, 11, 1, 1, 8999.00),
        (12, 12, 7, 2, 129.00)
    ]
    cursor.executemany("INSERT INTO order_items VALUES (?, ?, ?, ?, ?);", order_items_data)

    conn.commit()
    conn.close()
    print(f"[OK] Database initialized successfully at: {DB_PATH}")

if __name__ == "__main__":
    init_database()
