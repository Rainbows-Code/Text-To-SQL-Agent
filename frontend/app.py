"""
Streamlit 前端交互界面模块：智能 Text-to-SQL 数据分析 Agent 可视化工作台
基于 Session State 解决多组件重渲染状态保持问题
"""
import sys
from pathlib import Path

# 自动加入系统路径
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import pandas as pd
import streamlit as st

from app.agent import agent
from app.audit import audit_logger
from app.config import settings

# 1. 页面基本配置
st.set_page_config(
    page_title="Text-to-SQL 数据分析 Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. 页面标题与简介
st.title("🤖 Text-to-SQL 智能数据分析 Agent")
st.caption("基于 **Schema RAG + AST 安全防护 + 自自我修复闭环** 的工业级商业数据分析 Agent 平台")
st.markdown("---")

# 3. 侧边栏 (Sidebar)：系统健康状态与审计日志
with st.sidebar:
    st.header("⚙️ 系统控制台")
    
    st.subheader("💡 环境信息")
    st.write(f"**模型**: `{settings.LLM_MODEL}`")
    st.write(f"**数据库**: `{settings.abs_db_path.name}`")
    st.write(f"**最大修复轮次**: `{settings.MAX_REPAIR_TURNS}` 轮")
    
    st.markdown("---")
    st.subheader("📜 全流程审计日志")
    
    show_logs = st.checkbox("查看最新审计日志 (Recent Logs)", value=False)
    if show_logs:
        logs = audit_logger.get_recent_logs(limit=10)
        if logs:
            st.dataframe(pd.DataFrame(logs)[["timestamp", "question", "is_safe", "execution_time_ms", "row_count"]], use_container_width=True)
        else:
            st.info("暂无审计日志记录")

# 4. 主界面：快捷示例提问点选
st.subheader("💡 快捷示例问题 (点选试用)")
sample_questions = [
    "至今已支付的总销售额 (GMV) 是多少？",
    "各个城市的注册用户数量分别是多少？",
    "销量最高的前 3 个商品及其对应的销售总量是多少？",
    "每个商品类目的已支付销售总额是多少？",
    "消费总额最高的前 3 名用户姓名、所在城市及累积消费金额是多少？"
]

# 在 Session State 中管理输入的提问文本与查询结果
if "query_input" not in st.session_state:
    st.session_state["query_input"] = sample_questions[0]

if "query_result" not in st.session_state:
    st.session_state["query_result"] = None

cols = st.columns(len(sample_questions))
for idx, q_text in enumerate(sample_questions):
    if cols[idx].button(f"示例 {idx+1}", help=q_text):
        st.session_state["query_input"] = q_text
        st.session_state["query_result"] = None

# 5. 主提问输入框与分析按钮
query_text = st.text_input("请输入你的商业数据分析问题:", value=st.session_state["query_input"], key="user_question")
submit_btn = st.button("🚀 开始智能数据分析", type="primary", use_container_width=True)

# 6. 触发 Agent 闭环数据分析并保存至 session_state
if submit_btn and query_text.strip():
    with st.spinner("🤖 Agent 正在进行 Schema 检索、SQL 生成与只读数据库校验..."):
        # 调用核心闭环 Agent，将结果存盘至 session_state 避免二次点击刷新丢失
        st.session_state["query_result"] = agent.run_query(question=query_text.strip())

# 7. 渲染查询结果（无论交互怎么重绘，只要 query_result 存在就持续渲染）
res = st.session_state.get("query_result")
if res is not None:
    st.markdown("---")
    
    # 高风险查询二次确认预警弹窗
    if res.get("needs_confirmation"):
        st.warning("⚠️ **高风险查询预警**：系统检测到当前查询缺少 WHERE 条件，可能存在大表全表扫描风险！")
        for warning_msg in res.get("risk_warnings", []):
            st.error(f"- {warning_msg}")
        
        # 二次确认按钮控制（session_state 保护下勾选不会丢失查询结果）
        confirm_btn = st.checkbox("确认了解风险并继续展示数据", value=False, key="risk_confirm_checkbox")
        if not confirm_btn:
            st.stop()

    # 显示 Agent 分析结论与摘要
    if res["success"]:
        st.success("✅ **数据分析完成！**")
        
        # 指标卡片行
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("执行结果状态", "成功 (SUCCESS)")
        m2.metric("端到端总耗时", f"{res['execution_time_ms']:.2f} ms")
        m3.metric("结果总行数", f"{res['row_count']} 行")
        m4.metric("尝试修复轮次", f"{res['total_turns']} 轮")

        st.info(f"**分析结论摘要**: {res['explanation']}")

        st.subheader("📊 检索数据表")
        if res["rows"]:
            df = pd.DataFrame(res["rows"])
            st.dataframe(df, use_container_width=True)
        else:
            st.warning("查询执行成功，但数据库返回 0 条匹配记录。")

        st.subheader("💻 对应生成的 SQL 语句")
        st.code(res["final_sql"], language="sql")

        # 展示 Agent 重试与修补推演轨迹
        with st.expander("🔍 查看 Agent 自自我修复推演轨迹 (Turns Trajectory)"):
            st.json(res["repair_history"])

    else:
        st.error("❌ **分析失败，触发保护机制**")
        if res.get("human_handoff"):
            st.warning("🚨 **已自动触发【转人工介入 (Human Handoff)】流程**：系统已尝试多次自我修正仍报错，已为您将该失败任务派发给人工工程师跟进。")
        st.error(f"报错详情: {res['error']}")
        
        with st.expander("🔍 查看尝试履历与报错 Traceback"):
            st.json(res["repair_history"])
