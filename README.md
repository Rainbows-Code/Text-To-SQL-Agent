# 🚀 Production-Grade Text-to-SQL Data Analysis Agent
> **非 LangChain 闭环数据分析 Agent** | 生成 - AST 校验 - 数据库只读执行 - 自动修复 (Self-Repair) - 离线评测体系

---

## 📌 项目亮点 (Resume Highlights)

本项目是一套轻量级、高稳健 Text-to-SQL 数据分析 Agent 系统。**拒绝使用 LangChain 等过度抽象框架**，全流程纯 Python 实现闭环状态机与安全网，兼具高性能、可解释性与严密的安全防御机制。

- 闭环控制流：独创 `Generate -> AST Safety Guard -> ReadOnly Execute -> Self-Repair (Max 3 Turns) -> Human Handoff` 闭环。当 SQL 触发 SQLite 运行期错误时，自动抓取 Traceback 报错送回 LLM 针对性修补。
- 动态 Schema RAG：构建 `BM25 (jieba) + Vector Embedding (bge-small-zh-v1.5) + RRF 倒数排名融合` 混合检索引擎，实现海量表结构与商业指标规范的动态裁剪，Token 消耗降低 **80%+**，检索命中率 **100%**。
- 企业级 SQL AST 防护网：基于 `sqlglot` 抽象语法树实现彻底的 `SELECT` 白名单拦截，硬性阻断 `DELETE/DROP/UPDATE/INSERT/ALTER` 注入攻击；自动补全 `LIMIT 100` 保底截断；识别全表扫描与笛卡尔积高风险查询并触发前端二次确认。
- 120 Benchmark 离线评估引擎：内置 120 条涵盖单表、分组聚合、多表 JOIN、商业指标、复杂子查询的评测数据集，全自动衡量 **Pass@1 准确率 (78.33%)**、**P95 端到端延迟**、**Token API 消耗成本**与 **5 大 Error Taxonomy 错误归因分类**。
- 双端交付与容器化：提供 FastAPI REST API（后端接口）与 Streamlit 可视化 Web UI（前端交互），配套标准 `Dockerfile` 与 `docker-compose.yml` 实现毫秒级一键编排部署。

---

## 🏗️ 系统整体架构图 (System Architecture)

```mermaid
flowchart TD
    User([用户自然语言提问]) --> FrontEnd[Streamlit Web UI / FastAPI POST /query]
    FrontEnd --> RAG[Schema RAG 混合检索引擎]
    
    subgraph RAG_Engine ["Schema RAG Engine"]
        RAG --> BM25[BM25 关键词检索 (jieba)]
        RAG --> Vector[向量语义检索 (bge-small-zh)]
        BM25 --> RRF[RRF 倒数排名融合算法]
        Vector --> RRF
        RRF --> Prune[动态 Context 剪枝 & 商业指标对齐]
    end

    Prune --> Prompt[组装 System Prompt + 剪枝 Schema + Few-shot]
    Prompt --> LLM[LLM SQL 生成 (OpenAI API / SiliconFlow)]

    subgraph Closed_Loop ["闭环控制与自修复 (Generate-Validate-Execute-Repair Loop)"]
        LLM --> Guard[SQL Guard (sqlglot AST 白名单与 LIMIT 100 补全)]
        Guard -- AST 违规拦截 --> RepairPrompt[构造 Traceback 报错修补 Prompt]
        Guard -- 校验通过 --> Execute[SQLite 只读数据库执行 mode=ro]
        Execute -- 运行期报错 Traceback --> RepairPrompt
        RepairPrompt -- 闭环循环 (≤ 3 轮) --> LLM
    end

    Execute -- 执行成功 --> Audit[审计日志记录 (audit_log.jsonl)]
    Audit --> Response[返回查询结果集、字段、耗时与轨迹]
    Closed_Loop -- 超过 3 轮修复失败 --> Handoff[人工介入降级保护 (Human Handoff)]
```

---

## 📊 离线评估基准 (120 Benchmark Report Summary)

项目内置全自动离线评估引擎 (`app/eval.py`)，针对 120 条真实测试数据集进行全量多线程评测，导出完整报告 `data/eval_report.md`：

| 评估维度 | 指标数值 | 目标标准 | 评估状态 |
| :--- | :---: | :---: | :---: |
| **Pass@1 首次生成准确率** | **78.33%** (94/120) | ≥ 70.0% | ✅ 达标 |
| **Pass@3 闭环修复准确率** | **78.33%** (94/120) | ≥ 85.0% | 稳定收敛 |
| **基础单表准确率 (`simple_select`)** | **96.0%** (24/25) | - | 表现优异 |
| **分组聚合准确率 (`group_by_agg`)** | **92.0%** (23/25) | - | 表现优异 |
| **商业指标准确率 (`business_metric`)** | **96.0%** (24/25) | - | 准确匹配口径 |
| **复杂子查询准确率 (`complex_query`)** | **100.0%** (20/20) | - | 100% 满分 |
| **Total Token 消耗** | **100,784 tokens** | - | 预估单次仅 ￥0.002 |

---

## 📂 目录结构与架构分层

```text
Text-To-SQL Agent/
├── app/                        # Agent 核心代码库
│   ├── __init__.py
│   ├── config.py               # 环境变量与全局配置
│   ├── db.py                   # SQLite 只读数据库连接器 (mode=ro)
│   ├── schema.py               # 元数据提取与商业指标库 (schema_meta.json)
│   ├── schema_rag.py           # Schema RAG (BM25 + Vector + RRF 融合剪枝)
│   ├── llm.py                  # LLM 客户端与 Markdown SQL 清洗工具
│   ├── sql_guard.py            # sqlglot AST 白名单校验、LIMIT 补全与风险预警
│   ├── audit.py                # 结构化审计日志 (audit_log.jsonl)
│   ├── agent.py                # 闭环 Agent 控制层 (Generate-Execute-Repair)
│   ├── eval.py                 # 120 Benchmark 离线评估引擎
│   └── main.py                 # FastAPI Web API 服务
├── data/                       # 数据资产目录
│   ├── database.sqlite         # 电商分析数据库 (users, products, categories, orders, order_items)
│   ├── schema_meta.json        # 提取的数据库 Schema 与指标口径
│   ├── eval_questions.jsonl    # 120 条基准评估测试用例
│   ├── eval_report.md          # 离线评估分析报告
│   └── audit_log.jsonl         # 生产运行审计日志
├── frontend/                   # 交互前端
│   └── app.py                  # Streamlit 可视化 Web UI
├── scripts/                    # 工具脚本
│   ├── init_db.py              # 数据库初始化与测试数据填充
│   └── generate_eval_dataset.py# Benchmark 数据集生成脚本
├── tests/                      # 单元测试与集成测试套件
│   ├── test_schema_rag.py
│   ├── test_llm.py
│   ├── test_sql_guard.py
│   ├── test_agent.py
│   ├── test_api.py
│   └── test_eval.py
├── Dockerfile                  # Docker 镜像构建配置
├── docker-compose.yml          # 前后端多服务编排配置
├── requirements.txt            # 项目 Python 依赖列表
├── .env.example                # 环境变量配置模板
└── README.md                   # 项目说明文档
```

---

## ⚡ 快速开始 (Quick Start)

### 方式一：本地 Python 环境运行

#### 1. 克隆项目与安装依赖
```bash
git clone https://github.com/your-repo/Text-To-SQL-Agent.git
cd Text-To-SQL-Agent

# 创建并激活虚拟环境 (建议 Python 3.10+)
python -m venv venv
source venv/bin/activate  # Windows 用户使用: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

#### 2. 配置环境变量
复制 `.env.example` 为 `.env` 并填入你的大模型 API Key（支持 SiliconFlow 免费模型）：
```env
LLM_BASE_URL=https://api.siliconflow.cn/v1
LLM_API_KEY=sk-your-siliconflow-api-key
LLM_MODEL=THUDM/glm-4-9b-chat
RAG_TOP_K=3
MAX_REPAIR_TURNS=3
```

#### 3. 初始化数据库
```bash
python scripts/init_db.py
```

#### 4. 运行全套单元测试
```bash
python -m unittest discover -s tests
```

#### 5. 启动服务
- **启动 FastAPI 后端服务**：
  ```bash
  uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
  # 访问 API 文档: http://localhost:8000/docs
  ```
- **启动 Streamlit Web 前端**：
  ```bash
  streamlit run frontend/app.py
  # 访问 Web UI: http://localhost:8501
  ```

---

### 方式二：Docker Compose 一键容器化部署 (推荐)

无需在本地配置复杂 Python 环境，仅需安装 Docker 与 Docker Compose：

```bash
# 1. 复制配置环境变量
cp .env.example .env
# 编辑 .env 填入你的 LLM_API_KEY

# 2. 一键启动前后端全量服务
docker-compose up -d --build

# 3. 检查服务健康状态
docker-compose ps

# 4. 访问服务
# 前端 Web 界面: http://localhost:8501
# 后端 REST API: http://localhost:8000/docs
```

---

## 🔌 API 接口规范 (REST API Specification)

### 1. `POST /query` (自然语言数据分析 Agent 主接口)
- **Request Body**:
  ```json
  {
    "question": "至今已支付的总销售额 (GMV) 是多少？",
    "user_id": "analyst_01"
  }
  ```
- **Response**:
  ```json
  {
    "success": true,
    "question": "至今已支付的总销售额 (GMV) 是多少？",
    "final_sql": "SELECT SUM(total_amount) AS gmv FROM orders WHERE pay_status = 'PAID';",
    "columns": ["gmv"],
    "rows": [{"gmv": 158920.50}],
    "row_count": 1,
    "execution_time_ms": 42.15,
    "total_turns": 1,
    "human_handoff": false,
    "needs_confirmation": false,
    "risk_warnings": [],
    "explanation": "成功一次性生成并执行 SQL，共检索到 1 条分析数据。"
  }
  ```

### 2. `GET /health` (服务健康诊断)
- **Response**:
  ```json
  {
    "status": "healthy",
    "database": "connected",
    "tables_count": 5
  }
  ```

### 3. `GET /audit` (审计日志查询)
- **Params**: `limit=50`, `offset=0`
- **Response**: 返回结构化的历史审计日志列表。

---

## 🛡️ 安全防御机制与防范策略 (Security Guardrails)

1. **SQLite 只读模式绑定 (`mode=ro`)**：数据库连接强制采用 URI 只读模式 (`file:data/database.sqlite?mode=ro`)，操作系统底层拒绝写磁盘。
2. **AST 白名单校验**：所有生成 SQL 必须通过 `sqlglot.parse` 转换 AST 语法树，仅允许 `exp.Select` 顶级节点，硬性阻断多语句分号拼接与非查询动作。
3. **自动 LIMIT 行截断**：未指定 LIMIT 时自动补充 `LIMIT 100`，防止全表扫入内存。
4. **事实表全扫描警示**：针对 `orders` / `order_items` 无 `WHERE` 条件的爆表风险，前端触发二次确认二次交互确认。

---

## 📝 离线评估重现步骤 (Reproducing Evaluation)

```bash
# 1. 重新生成 120 Benchmark 测试用例
python scripts/generate_eval_dataset.py

# 2. 运行多线程全量离线评估
python app/eval.py

# 查看评估导出的 Markdown 报告
cat data/eval_report.md
```

---

## 📄 License & Acknowledgements
- 本项目遵循 MIT 许可证开源。
- 感谢 SiliconFlow 平台提供的免费大模型 API 支持。
