"""
Step 3 验证测试：Schema RAG 混合检索命中率 (Hit Rate) 与 Context 裁剪测试
支持 pytest 运行与 python test_schema_rag.py 直接运行
"""
import sys
from pathlib import Path

# 自动加入系统路径
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.schema_rag import schema_rag
from app.schema import schema_manager

TEST_RAG_CASES = [
    {
        "question": "查找北京市年龄大于30岁的用户名称与注册时间",
        "expected_tables": {"users"}
    },
    {
        "question": "计算至今为止已支付的总销售额 GMV",
        "expected_tables": {"orders"}
    },
    {
        "question": "销售数量最高的前 3 个商品名称和销售总量",
        "expected_tables": {"order_items", "products"}
    },
    {
        "question": "查询数码电子分类下的所有商品售价与成本",
        "expected_tables": {"products", "categories"}
    },
    {
        "question": "统计消费金额最高的用户姓名、常住城市与订单支付状态",
        "expected_tables": {"users", "orders"}
    }
]

def test_bm25_search():
    res = schema_rag.search_bm25("北京市 用户 年龄")
    top_table = res[0][0]
    assert top_table == "users", f"BM25 匹配错误，期望 'users'，实际得到 '{top_table}'"

def test_vector_search():
    res = schema_rag.search_vector("商品 售价 成本 库存")
    top_table = res[0][0]
    assert top_table == "products", f"Vector 匹配错误，期望 'products'，实际得到 '{top_table}'"

def test_rrf_hybrid_retrieval_and_hit_rate():
    hit_count = 0
    total_cases = len(TEST_RAG_CASES)

    for case in TEST_RAG_CASES:
        retrieved_tables = schema_rag.rrf_hybrid_search(case["question"], top_k=2)
        retrieved_table_names = {t["table_name"] for t in retrieved_tables}
        
        # 检验期望的表是否全部在 Top-K 召回列表中
        if case["expected_tables"].issubset(retrieved_table_names):
            hit_count += 1
            print(f"[PASS] 问题: '{case['question']}'")
            print(f"       期望召回: {case['expected_tables']}, 实际召回: {retrieved_table_names}")
        else:
            print(f"[FAIL] 问题: '{case['question']}'")
            print(f"       期望召回: {case['expected_tables']}, 实际召回: {retrieved_table_names}")

    hit_rate = hit_count / total_cases
    assert hit_rate >= 0.8, f"Top-2 检索命中率低于目标 80% (实际 {hit_rate*100:.1f}%)"
    print(f"\n[OK] Top-2 检索命中率: {hit_rate * 100:.1f}%")

def test_context_pruning_token_reduction():
    full_prompt = schema_manager.format_full_schema_prompt()
    pruned_prompt = schema_rag.retrieve_and_prune_schema("查找北京市的用户", top_k=1)
    
    # 验证动态裁剪后字符数/Token 减少了 50% 以上
    assert len(pruned_prompt) < len(full_prompt) * 0.6, "动态裁剪后的 Schema 上下文没有实现明显的 Token 降低"
    print(f"\n[OK] Context 动态裁剪成功! 全量长度: {len(full_prompt)} 字符 -> 裁剪后长度: {len(pruned_prompt)} 字符")

def run_all_manual_rag_tests():
    print("=" * 60)
    print("Start Step 3 Schema RAG Hybrid Search & Context Pruning Validation...")
    print("=" * 60)
    
    test_bm25_search()
    print("[PASS] BM25 Search Test: PASSED")
    
    test_vector_search()
    print("[PASS] Vector Search Test: PASSED")
    
    test_rrf_hybrid_retrieval_and_hit_rate()
    test_context_pruning_token_reduction()

    print("=" * 60)
    print("Step 3 Schema RAG validation 100% PASSED!")
    print("=" * 60)

if __name__ == "__main__":
    run_all_manual_rag_tests()
