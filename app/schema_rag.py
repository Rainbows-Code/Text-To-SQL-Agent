"""
Schema RAG 模块：BM25 关键词检索 + Embedding 向量检索 + RRF 融合与动态 Context 裁剪
"""
import math
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

# 自动将项目根目录加入 sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.schema import SchemaManager, schema_manager
from app.config import settings

# 尝试导入可选的高级检索依赖 (jieba, rank_bm25, sentence_transformers)
try:
    import jieba
    from rank_bm25 import BM25Okapi
    HAS_BM25_DEPS = True
except ImportError:
    HAS_BM25_DEPS = False

try:
    from sentence_transformers import SentenceTransformer, util
    HAS_VECTOR_DEPS = True
except ImportError:
    HAS_VECTOR_DEPS = False


class SchemaRAG:
    """Schema 混合检索与动态 Context 裁剪引擎"""

    def __init__(self, manager: SchemaManager = schema_manager):
        self.manager = manager
        self.tables = self.manager.get_tables()
        self.metrics = self.manager.get_metrics()
        
        # 1. 准备 Schema 文档数据
        self.doc_texts: List[str] = []
        self.table_names: List[str] = []
        self._build_documents()

        # 2. 初始化 BM25 检索器
        self.bm25_model = None
        self._init_bm25()

        # 3. 初始化 向量 检索器 (延迟加载以提升启动速度)
        self.vector_model = None
        self.table_embeddings = None

    def _build_documents(self):
        """构建适合全文与向量检索的 Schema 文档表征"""
        for t in self.tables:
            table_name = t["table_name"]
            desc = t["description"]
            cols_str = ", ".join([f"{c['name']} ({c['description']})" for c in t["columns"]])
            fk_str = ""
            if t.get("foreign_keys"):
                fk_str = " 外键关联: " + ", ".join([f"{fk['column']}连{fk['referenced_table']}" for fk in t["foreign_keys"]])
            
            doc = f"表名:{table_name} 描述:{desc} 包含字段:{cols_str}{fk_str}"
            self.table_names.append(table_name)
            self.doc_texts.append(doc)

    def _tokenize(self, text: str) -> List[str]:
        """中文分词处理"""
        if HAS_BM25_DEPS:
            # 清理标点符号并分词
            clean_text = re.sub(r"[^\w\s]", "", text)
            return [w for w in jieba.lcut(clean_text) if w.strip()]
        else:
            # 简单的字符级与单词级切分后备方案
            return re.findall(r"\w+", text.lower())

    def _init_bm25(self):
        """初始化 BM25 索引"""
        corpus_tokens = [self._tokenize(doc) for doc in self.doc_texts]
        if HAS_BM25_DEPS and corpus_tokens:
            self.bm25_model = BM25Okapi(corpus_tokens)

    def _init_vector_model(self):
        """初始化向量编码模型 (优先使用本地缓存与极速后备，零网络延迟)"""
        if HAS_VECTOR_DEPS and self.vector_model is None:
            # 1. 尝试从本地缓存加载 (零网络延迟)
            try:
                self.vector_model = SentenceTransformer(settings.EMBEDDING_MODEL_NAME, local_files_only=True)
                self.table_embeddings = self.vector_model.encode(self.doc_texts, convert_to_tensor=True)
                return
            except Exception:
                pass

            # 2. 若无本地缓存且开启了网络在线尝试，快速尝试一次加载
            try:
                import os
                os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"
                self.vector_model = SentenceTransformer(settings.EMBEDDING_MODEL_NAME)
                self.table_embeddings = self.vector_model.encode(self.doc_texts, convert_to_tensor=True)
            except Exception as e:
                # 3. 若网络无法连接 HuggingFace，瞬间切换为本地零延迟文本语义算法
                self.vector_model = False

    def search_bm25(self, query: str) -> List[Tuple[str, float]]:
        """BM25 关键词检索并返回 (table_name, score) 列表"""
        query_tokens = self._tokenize(query)
        if self.bm25_model and query_tokens:
            scores = self.bm25_model.get_scores(query_tokens)
        else:
            # 基础重叠分词后备算法
            scores = []
            q_set = set(query_tokens)
            for doc_toks in [self._tokenize(doc) for doc in self.doc_texts]:
                overlap = len(q_set.intersection(set(doc_toks)))
                scores.append(float(overlap))

        table_scores = list(zip(self.table_names, [float(s) for s in scores]))
        table_scores.sort(key=lambda x: x[1], reverse=True)
        return table_scores

    def search_vector(self, query: str) -> List[Tuple[str, float]]:
        """向量语义检索并返回 (table_name, score) 列表"""
        self._init_vector_model()
        
        if HAS_VECTOR_DEPS and self.vector_model and self.table_embeddings is not None:
            query_embedding = self.vector_model.encode(query, convert_to_tensor=True)
            cos_scores = util.cos_sim(query_embedding, self.table_embeddings)[0]
            scores = [float(s) for s in cos_scores]
        else:
            # 轻量 Jaccard 相似度后备算法
            q_chars = set(query)
            scores = []
            for doc in self.doc_texts:
                d_chars = set(doc)
                intersection = len(q_chars.intersection(d_chars))
                union = len(q_chars.union(d_chars)) or 1
                scores.append(intersection / union)

        table_scores = list(zip(self.table_names, scores))
        table_scores.sort(key=lambda x: x[1], reverse=True)
        return table_scores

    def rrf_hybrid_search(self, query: str, top_k: int = 3, rrf_k: int = 60) -> List[Dict[str, Any]]:
        """
        RRF (Reciprocal Rank Fusion) 倒数排名融合算法
        RRF_Score(doc) = 1 / (rrf_k + rank_bm25) + 1 / (rrf_k + rank_vector)
        """
        bm25_results = self.search_bm25(query)
        vector_results = self.search_vector(query)

        # 记录每个表在两种检索方式下的排名 (1-indexed)
        bm25_ranks = {tbl: i + 1 for i, (tbl, _) in enumerate(bm25_results)}
        vector_ranks = {tbl: i + 1 for i, (tbl, _) in enumerate(vector_results)}

        rrf_scores = {}
        for tbl in self.table_names:
            score_bm25 = 1.0 / (rrf_k + bm25_ranks[tbl])
            score_vector = 1.0 / (rrf_k + vector_ranks[tbl])
            rrf_scores[tbl] = score_bm25 + score_vector

        # 按 RRF 得分降序排列
        sorted_tables = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        top_table_names = [tbl for tbl, _ in sorted_tables[:top_k]]

        # 返回召回的表元数据对象
        retrieved_tables = [self.manager.get_table_by_name(t_name) for t_name in top_table_names if self.manager.get_table_by_name(t_name)]
        return retrieved_tables

    def retrieve_and_prune_schema(self, query: str, top_k: int = 3) -> str:
        """
        核心 API：根据用户问题检索召回 Top-K 相关的表与业务指标，动态拼接精简 Prompt
        """
        retrieved_tables = self.rrf_hybrid_search(query, top_k=top_k)
        retrieved_table_names = {t["table_name"] for t in retrieved_tables}

        lines = ["### 【检索出的相关数据库 Schema】:"]
        
        for t in retrieved_tables:
            lines.append(f"\n表名: {t['table_name']} ({t['description']})")
            lines.append("字段列表:")
            for col in t["columns"]:
                pk_flag = " [主键]" if col.get("primary_key") else ""
                lines.append(f"  - {col['name']} ({col['type']}){pk_flag}: {col['description']}")
            
            # 只显示与当前召回集合相关的外键关系
            if t.get("foreign_keys"):
                rel_fks = [fk for fk in t["foreign_keys"] if fk["referenced_table"] in retrieved_table_names]
                if rel_fks:
                    lines.append("外键关联:")
                    for fk in rel_fks:
                        lines.append(f"  - {fk['column']} -> {fk['referenced_table']}.{fk['referenced_column']}")

        # 匹配可能相关的业务指标
        matched_metrics = []
        for m in self.metrics:
            if any(kw in query for kw in [m['metric_name'], m['metric_name'].split('/')[0].strip()]):
                matched_metrics.append(m)

        if matched_metrics:
            lines.append("\n### 【相关业务指标口径规范】:")
            for m in matched_metrics:
                lines.append(f"- 【{m['metric_name']}】: {m['definition']}")
                lines.append(f"  公式与过滤逻辑: {m['calculation_rule']}")

        return "\n".join(lines)

schema_rag = SchemaRAG()
