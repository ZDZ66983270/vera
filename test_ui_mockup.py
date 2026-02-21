import streamlit as st
import time
import datetime

# 设置页面为宽屏模式，并使用深色主题的基调
st.set_page_config(layout="wide", page_title="VERA 资产评估优化")

# --- 自定义 CSS (用于改变按钮颜色和一些样式微调) ---
# Streamlit 原生不支持修改按钮颜色，这里使用 CSS Hack 将主按钮改为蓝色
st.markdown("""
<style>
    /* 将第一个 stButton (运行分析) 的颜色改为蓝色 */
    div.stButton > button:first-child {
        background-color: #007bff; /* 专业的科技蓝 */
        color: white;
        border: none;
        font-weight: bold;
        padding: 0.5rem 1rem;
    }
    div.stButton > button:first-child:hover {
        background-color: #0056b3; /* 悬停加深 */
        border: none;
        color: white;
    }
    /* 调整一下输入框的标签样式，使其更紧凑 */
    .stTextInput label, .stDateInput label {
        font-size: 14px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# --- 模拟侧边栏 (简化版) ---
with st.sidebar:
    st.title("VERA")
    st.caption("Value & Risk Assessment System")
    st.markdown("---")
    st.radio("功能导航", ["欢迎 (Welcome)", "资产分析 (Analysis)", "资产管理 (Universe)"], index=1)

# --- 主界面优化区域 ---

st.subheader("📈 资产评估")
st.markdown("#### 🔍 选择要分析的资产")

# --- 布局优化核心：使用列 (Columns) 将输入项并排 ---
col1, col2 = st.columns([3, 1]) # 左侧搜索框占3份宽度，右侧日期占1份

with col1:
    # 合并为一个智能输入框，提示更明确
    ticker_input = st.text_input("资产搜索 (输入代码或名称)", placeholder="例如: TSLA 或 Tesla...", value="TSLA")
    # 即时反馈 (模拟)
    if ticker_input and ticker_input.upper() == 'TSLA':
        st.caption("✅ 已匹配: Tesla Inc. (NASDAQ)")

with col2:
    # 日期选择器放在右侧
    valuation_date = st.date_input("评估基准日", value=datetime.date(2026, 1, 5))

# 增加一点间距
st.write("")

# --- 操作按钮 ---
# 这个按钮现在会被上面的 CSS 渲染成蓝色
run_button = st.button("▶ 运行分析", use_container_width=True)

# --- 交互逻辑与优雅的错误提示 ---
if run_button:
    # 模拟一个加载过程
    with st.spinner('正在分析数据，请稍候...'):
        time.sleep(1.5) # 假装在计算

    # 模拟一个错误情况 (复现您图中的错误)
    # 使用 st.toast 而不是巨大的 st.error 色块
    st.toast(f"❌ 无法获取 {ticker_input.upper()} 在 {valuation_date} 之前的数据。", icon="⚠️")

st.markdown("---")
st.button("↩ 返回历史记录")
