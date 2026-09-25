"""
Step 7 验证测试：FastAPI RESTful API 路由连通性与 JSON Schema 测试
支持 pytest 运行与 python test_api.py 直接运行
"""
import sys
from pathlib import Path

# 自动接入系统路径
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_endpoint():
    """测试 /health 健康检查接口"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "database" in data
    print(f"\n[PASS] GET /health 健康检查校验通过! 数据库状态: {data['database']}")

def test_audit_endpoint():
    """测试 /audit 审计日志接口"""
    response = client.get("/audit?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert "logs" in data
    print(f"[PASS] GET /audit 日志查询接口校验通过! 查到条目数: {data['total_records']}")

def test_query_endpoint():
    """测试 POST /query 分析接口"""
    payload = {
        "question": "至今已支付的总销售额 (GMV) 是多少？",
        "user_id": "test_user_api"
    }
    response = client.post("/query", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "success" in data
    assert "final_sql" in data
    assert "columns" in data
    print(f"[PASS] POST /query 接口校验通过! 响应字段完整.")

def run_all_api_tests():
    print("=" * 60)
    print("Start Step 7 FastAPI REST API Validation...")
    print("=" * 60)
    
    test_health_endpoint()
    test_audit_endpoint()
    test_query_endpoint()

    print("=" * 60)
    print("Step 7 FastAPI REST API validation 100% PASSED!")
    print("=" * 60)

if __name__ == "__main__":
    run_all_api_tests()
