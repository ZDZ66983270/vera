"""
VERA - Value & Risk Assessment System
=====================================

## 核心功能：PDF 财报智能导入 (Financial Report PDF Import)

### 1. 核心流程 (Core Workflow)
   - **解析 (Parsing)**: 使用 `pdfplumber` 提取 PDF 文本，支持文本层提取与 OCR 模式 (通过 `utils/ocr_engine.py`)。
   - **关键词匹配 (Keyword Matching)**: 
     - 采用集中式配置 (`config/bank_keywords.py`) 管理所有指标关键词。
     - 支持 **通用关键词** 与 **银行特定关键词** (如招行“贷款和垫款”) 的自动合并策略。
   - **数值提取 (Extraction)**:
     - `utils/pdf_engine.py`: 通过正则搜索数值，支持中文大写数字与 "亿/万" 单位换算。
     - **噪音过滤**: 针对 `is_large=True` 的大额指标 (如资产、营收)，自动过滤小于 1000 万的数值，防止脚注编号干扰。
     - **优先级策略**: 支持 `nearest` (最近距离) 和 `largest` (最大值) 两种策略，确保合并报表数据的优先提取。
   - **日期识别 (Date Detection)**:
     - 优先识别 "截至 xxxx 年 xx 月 xx 日"。
     - 智能推断 "一季度/半年度/三季度/年报" 对应的会计周期 (03-31, 06-30, 09-30, 12-31)。

### 2. 关键文件 (Key Files)
   - `app.py`: 主界面与交互逻辑，包含导入页面的状态反馈 (成功/缺失指标提示)。
   - `utils/pdf_engine.py`: PDF 解析引擎，实现指标搜索、单位归一化与过滤逻辑。
   - `config/bank_keywords.py`: 指标关键词映射表 (Single Source of Truth)。
   - `utils/batch_image_processor.py`: 批量处理入口，连接 UI 与解析引擎，并负责写入数据库。

### 3. 数据存储 (Data Storage)
   - 写入 `financial_history` 表，支持多次导入的覆盖更新 (Upsert)。
   - 区分数据来源优先级: PDF_OCR_HIGH > CSV_IMPORT > IMAGE_OCR。

(Last Updated: 2026-01-30)
"""
import streamlit as st
# Asset Sorting Rules (Reflected in database ORDER BY):
# 1. Market Priority: HK (0) > US (1) > CN (2) > Other (3)
#    市场优先级：港股 (HK) > 美股 (US) > A股 (CN) > 其他
# 2. Type Priority: Equity/Stock (0) > ETF (1) > Index (2) > Other (3)
#    类型优先级：个股 > ETF > 指数
# 3. Code Order: Alphanumeric Ascending
#    代码顺序：按字符/数字顺序排列

import textwrap
import pandas as pd
from typing import Optional
from datetime import datetime, timedelta
from engine.snapshot_builder import run_snapshot
from analysis.dashboard import DashboardData, get_asset_name
from engine.universe_manager import get_universe_assets_v2, add_to_universe
from db.connection import get_connection
from analysis.risk_profile import get_current_profile, save_user_profile, reset_profile, RiskProfile
from utils.i18n import translate, get_translation, get_legend_text
from vera.mappings import get_u_state_def, get_o_state_def
from metrics.recent_cycle_engine import RecentCycleEngine, RecentCycleInfo
from metrics.risk_engine import RiskEngine
from typing import Optional, Dict, Any, Tuple

def normalize_position_display(
    *,
    percentile: Optional[float],
    window_label: str = "10Y",     # "10Y" or "ALL" (configurable)
    near_peak: float = 0.95,
    near_trough: float = 0.05,
) -> Dict[str, Any]:
    """
    Single source of truth for Position display.
    Rules (frozen):
      - >=95%: show text "阶段高点" (no percentage)
      - <=5% : show text "阶段低点" (no percentage)
      - else : show percent like "67%"
      - None : "-"
    """
    if percentile is None:
        return {
            "label_code": "NA",
            "display": "-",
            "display_pct": None,
            "tooltip": f"History Percentile: N/A ({window_label})",
            "window_label": window_label,
        }

    # clamp to [0,1] just in case
    p = max(0.0, min(1.0, float(percentile)))

    if p >= near_peak:
        display = "阶段高点"
        code = "PEAK"
        display_pct = None
    elif p <= near_trough:
        display = "阶段低点"
        code = "TROUGH"
        display_pct = None
    else:
        display = f"{p*100:.0f}%"
        code = "PCTL"
        display_pct = p

    return {
        "label_code": code,  # PEAK | TROUGH | PCTL | NA
        "display": display,
        "display_pct": display_pct,
        "tooltip": f"History Percentile: {p*100:.0f}% ({window_label})",
        "window_label": window_label,
    }

# 设置页面配置 (必须是第一个 Streamlit 命令)
st.set_page_config(
    page_title="VERA 智能投研",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# VERA UI Styles
st.markdown("""
<style>
    /* Google Fonts Import */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Noto+Sans+SC:wght@300;400;500;700&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200');

    /* Theme Variables (Dracula-ish / Tailwind Slate Dark) */
    :root {
        --bg-dark: #0b0c0e;
        --card-dark: #1a1d23;
        --border-dark: #2d3748; /* slate-800 approx */
        --text-main: #f1f5f9; /* slate-100 */
        --text-muted: #94a3b8; /* slate-400 */
        --primary: #3b82f6; /* blue-500 */
        --risk-red: #ef4444; /* red-500 */
        --safe-green: #22c55e; /* green-500 */
        --gold: #eab308; /* yellow-500 */
    }

    /* Global Overrides */
    .stApp {
        font-family: 'Inter', 'Noto Sans SC', sans-serif !important;
        background-color: var(--bg-dark);
    }
    
    /* Utility Classes (Tailwind-like) */
    .text-slate-400 { color: #94a3b8 !important; }
    .text-slate-500 { color: #64748b !important; }
    .text-white { color: #ffffff !important; }
    .bg-card { background-color: var(--card-dark); }
    .border-slate-800 { border-color: #1e293b !important; }
    .rounded-xl { border-radius: 0.75rem !important; }
    .p-6 { padding: 1.5rem !important; }
    .gap-6 { gap: 1.5rem !important; }\n\n    /* Expert Mode Visuals */\n    .expert-mode-banner {\n        background: linear-gradient(90deg, #1e3a8a 0%, #3b82f6 100%);\n        color: white;\n        padding: 16px 24px;\n        border-radius: 12px;\n        margin-bottom: 24px;\n        display: flex;\n        justify-content: space-between;\n        align-items: center;\n        box-shadow: 0 4px 20px rgba(59, 130, 246, 0.5);\n        animation: pulse-blue 2s infinite;\n    }\n    @keyframes pulse-blue {\n        0% { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.7); }\n        70% { box-shadow: 0 0 0 15px rgba(59, 130, 246, 0); }\n        100% { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0); }\n    }\n    .expert-overlay-border {\n        position: fixed;\n        top: 0; left: 0; width: 100%; height: 100%;\n        pointer-events: none;\n        z-index: 99999;\n        border: 4px solid rgba(59, 130, 246, 0.3);\n        box-sizing: border-box;\n    }\n    .expert-detail-text {\n        font-size: 0.75rem;\n        color: #60a5fa;\n        margin-top: 6px;\n        font-family: monospace;\n        background: rgba(59, 130, 246, 0.1);\n        padding: 4px 8px;\n        border-radius: 4px;\n        display: inline-block;\n        border-left: 2px solid #3b82f6;\n    }\n
    
    .vera-card {
        background-color: var(--card-dark);
        border: 1px solid var(--border-dark);
        border-radius: 0.75rem; /* rounded-xl */
        box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
        overflow: visible; /* Changed from hidden to allow tooltip overflow */
        margin-bottom: 24px;
    }
    
    /* Make st.container(border=True) match .vera-card */
    [data-testid="stVerticalBlockBorderWrapper"] {
        background-color: var(--card-dark) !important;
        border: 1px solid var(--border-dark) !important;
        border-radius: 0.75rem !important;
        box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05) !important;
        margin-bottom: 24px !important;
    }

    /* Remove default padding ONLY for containers with a card header inside */
    [data-testid="stVerticalBlockBorderWrapper"]:has(.vera-card-header) {
        padding: 0 !important;
    }

    .vera-card-header {
        padding: 16px 24px;
        background-color: transparent; /* Cleaner flat look */
        border-bottom: none;
        display: flex;
        align-items: center;
    }
    
    .vera-card-body {
        padding: 24px;
        display: grid;
        grid-template-columns: repeat(3, 1fr); /* Equal 3-column layout */
        gap: 32px;
        align-items: center;
    }

    /* Column 0: Verdict */
    .verdict-box {
        text-align: center;
        padding-right: 32px;
        border-right: none !important;
    }
    .verdict-badge {
        display: inline-block;
        padding: 8px 16px;
        border-radius: 6px;
        font-weight: 700;
        font-size: 1.125rem;
        margin: 8px 0;
        border: 2px solid;
    }
    .badge-red { border-color: #ef4444; color: #ffffff; background: #ef4444; }
    .badge-green { border-color: #22c55e; color: #22c55e; background: rgba(34, 197, 94, 0.1); }
    .badge-yellow { border-color: #eab308; color: #eab308; background: rgba(234, 179, 8, 0.1); }
    
    /* Column 1: Reasoning */
    .reasoning-box {
        padding: 0 16px;
        overflow-wrap: break-word;
        word-break: break-word;
    }
    .reasoning-title {
        font-size: 1.25rem;
        font-weight: 600;
        color: var(--text-main);
        margin-bottom: 8px;
    }
    .reasoning-sub {
        font-size: 0.875rem;
        color: var(--text-muted);
    }
    
    /* Column 2: Action Gate */
    .action-box {
        padding-left: 32px;
        border-left: none !important;
    }
    .action-item {
        display: flex;
        align-items: center;
        font-size: 0.875rem;
        color: var(--text-muted);
        margin-bottom: 6px;
    }
    .action-denied {
        text-decoration: line-through;
        opacity: 0.7;
    }
    .action-allowed {
        color: var(--safe-green);
        font-weight: 500;
    }

    /* Risk Overlay Grid */
    .risk-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 24px;
        width: 100%;
    }
    .risk-card {
        background-color: var(--card-dark);
        border: 1px solid var(--border-dark);
        border-radius: 0.75rem;
        display: flex;
        flex-direction: column;
        height: 100%;
    }
    .risk-card-header {
        padding: 16px;
        border-bottom: 1px solid var(--border-dark);
        background-color: rgba(15, 23, 42, 0.3); /* slate-900/50 */
    }
    .risk-card-body {
        padding: 20px;
        flex: 1;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    
    /* Progress Bar */
    .progress-track {
        height: 6px;
        width: 100%;
        background-color: #334155; /* slate-700 */
        border-radius: 9999px;
        overflow: hidden;
        margin-top: 16px;
    }
    .progress-fill {
        height: 100%;
        border-radius: 9999px;
    }
    
    /* Material Icons Helper */
    .material-symbols-outlined {
        font-family: 'Material Symbols Outlined';
        font-weight: normal;
        font-style: normal;
        font-size: 18px;
        line-height: 1;
        letter-spacing: normal;
        text-transform: none;
        display: inline-block;
        white-space: nowrap;
        word-wrap: normal;
        direction: ltr;
        vertical-align: middle;
    }
    
    /* Tooltip Overlay */
    .vera-tooltip {
        position: relative;
        cursor: help;
        border-bottom: 1px dotted rgba(148, 163, 184, 0.5); /* Subtle indicator */
    }
    
    .vera-tooltip .vera-tooltip-text {
        visibility: hidden;
        width: 320px;
        background-color: #1e293b; /* slate-800 */
        color: #f1f5f9;
        text-align: left;
        border-radius: 8px;
        padding: 12px;
        
        /* Positioning: Bottom Right relative to trigger */
        position: absolute;
        z-index: 1000; /* High z-index */
        top: 100%; /* Below the element */
        left: 0; /* Align left edge first */
        margin-top: 8px;
        
        /* Shadows and Borders */
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.5), 0 4px 6px -2px rgba(0, 0, 0, 0.3);
        border: 1px solid #334155; /* slate-700 */
        
        /* Typography */
        font-size: 0.75rem;
        line-height: 1.5;
        white-space: normal; /* Allow wrapping */
        font-weight: 400;
        
        /* Animation */
        opacity: 0;
        transition: opacity 0.2s;
    }
    
    .vera-tooltip:hover .vera-tooltip-text {
        visibility: visible;
        opacity: 1;
    }
    
    /* Strong tags inside tooltip */
    .vera-tooltip-text strong, .metric-help-overlay strong {
        color: #60a5fa; /* blue-400 */
        font-weight: 600;
    }
    
    .vera-tooltip-text ul, .metric-help-overlay ul {
        margin: 0;
        padding-left: 16px;
        list-style-type: disc;
    }
    
    .vera-tooltip-text li, .metric-help-overlay li {
        margin-bottom: 6px;
    }
    .metric-help-overlay {
        display: none;
        position: absolute;
        bottom: 120%; /* Place above the element */
        left: 50%;
        transform: translateX(-50%); /* Center horizontally */
        width: 320px; /* Fixed reasonable width */
        background: #1e293b; /* slate-800 */
        border: 1px solid #475569; /* slate-600 */
        padding: 16px;
        border-radius: 8px;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.6), 0 8px 10px -6px rgba(0, 0, 0, 0.6);
        color: #e2e8f0;
        font-size: 0.8rem;
        z-index: 9999; /* Ensure on top */
        line-height: 1.6;
        pointer-events: none;
        white-space: normal;
    }
    .metric-help-overlay::after {
        content: "";
        position: absolute;
        top: 100%;
        left: 50%;
        margin-left: -6px;
        border-width: 6px;
        border-style: solid;
        border-color: #475569 transparent transparent transparent;
    }
    .vera-tooltip-trigger {
        position: relative; /* Ensure anchor */
    }
    .vera-tooltip-trigger:hover .metric-help-overlay {
        display: block;
        animation: fadeInTooltip 0.2s ease-out;
    }
    @keyframes fadeInTooltip {
        from { opacity: 0; transform: translate(-50%, 10px); }
        to { opacity: 1; transform: translate(-50%, 0); }
    }
</style>
""", unsafe_allow_html=True)

def render_vera_top_decision_area(result):
    """
    Renders the VERA Top Decision Area with a 3-row structured layout:
    Row 1: Verdict + Facts
    Row 2: Regime + Unlock Conditions
    Row 3: Action Gate (Permitted Actions)
    """
    if not result or "error" in result:
         st.warning(f"VERA Engine: {result.get('error', 'Unknown Error')}")
         return

    u = result.get("underlying", {})
    o = result.get("options", {})
    d = result.get("decision", {})
    
    r_state = d.get("R_state", "UNKNOWN")
    u_label = u.get("U_state_label", "未知")
    o_label = o.get("O_state_label", "未知")
    u_state = u.get("U_state", "UNKNOWN")
    o_state = o.get("O_state", "UNKNOWN")
    
    # Metrics for Facts
    iv_pct = o.get("iv_now_pct", 0.0)
    m = u.get("metrics", {})
    daily_ret = m.get("daily_ret", 0.0)
    vol_ratio = m.get("vol_ratio", 0.0)
    cp = m.get("close_pos", 0.0)

    # 1. Title
    st.markdown('<div style="font-size:1.1rem; font-weight:700; color:#e2e8f0; margin-bottom:16px;">🧠 VERA 核心决策 (Decision Engine)</div>', unsafe_allow_html=True)

    # --- ROW 1: Verdict + Key Metrics ---
    c1, c2 = st.columns([2, 1], gap="medium")
    
    with c1:
        # Permission Card
        bg_color = "rgba(239, 68, 68, 0.1)" # Red
        border_color = "rgba(239, 68, 68, 0.4)"
        text_color = "#ef4444"
        if r_state == "GREEN":
            bg_color = "rgba(34, 197, 94, 0.1)"
            border_color = "rgba(34, 197, 94, 0.4)"
            text_color = "#22c55e"
        elif r_state == "YELLOW":
            bg_color = "rgba(234, 179, 8, 0.1)"
            border_color = "rgba(234, 179, 8, 0.4)"
            text_color = "#eab308"

        # Build Risk Tags HTML early to inject into the card
        tags = d.get("risk_tags", [])
        tag_html = ""
        if tags:
            tag_map = {
                "CIRCUIT_BREAKER": ("🛑 交易熔断", "#ef4444"),
                "EXTREME_VOL": ("🌊 波动率极值", "#f97316"), # Orange
                "TREND_UNSTABLE": ("📉 趋势不稳", "#3b82f6"), # Blue
                "LOW_MOMENTUM": ("⏳ 动能不足", "#94a3b8"),   # Gray
                "HIGH_PREMIUM": ("⚠️ 高 IV 溢价", "#eab308")   # Yellow
            }
            tag_list_html = ""
            for t in tags:
                label, color = tag_map.get(t, (t, "#64748b"))
                tag_list_html += f'<span style="background:{color}22; color:{color}; border:1px solid {color}44; padding:2px 10px; border-radius:100px; font-size:0.75rem; font-weight:600; margin-right:8px; margin-top:8px;">{label}</span>'
            tag_html = f'<div style="display:flex; flex-wrap:wrap; margin-top:16px; border-top:1px solid rgba(255,255,255,0.05); padding-top:12px;">{tag_list_html}</div>'

        st.markdown(f"""
        <div style="background:{bg_color}; border:1px solid {border_color}; border-radius:12px; padding:24px; min-height:160px; display:flex; flex-direction:column; justify-content:center;">
            <div style="font-size:0.75rem; color:{text_color}; text-transform:uppercase; font-weight:700; margin-bottom:8px;">最终结论 (Final Verdict)</div>
            <div style="font-size:1.75rem; font-weight:800; color:{text_color}; margin-bottom:8px;">{d.get('summary_label_zh', '无法裁定')}</div>
            <div style="font-size:0.95rem; color:#94a3b8; line-height:1.5;">{d.get('summary_note_zh', '正在获取系统提示...')}</div>
            {tag_html}
        </div>
        """, unsafe_allow_html=True)

    with c2:
        # Key Metrics Card (Facts)
        def _fmt_fact(label, val, unit="", help_text=""):
            help_html = ""
            label_cls = ""
            if help_text:
                label_cls = "vera-tooltip-trigger" # Use existing tooltip class
                help_html = f'<span class="vera-help-icon" style="margin-left:4px; font-size:0.8rem;">ⓘ</span><div class="metric-help-overlay" style="width:200px; right:0; left:auto;">{help_text}</div>'
            
            return f'<div style="display:flex; justify-content:space-between; margin-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.05); padding-bottom:4px;"><span class="{label_cls}" style="color:#64748b; font-size:0.85rem; position:relative; cursor:help;">{label}{help_html}</span><span style="color:#f1f5f9; font-weight:600; font-family:monospace;">{val}{unit}</span></div>'

        # Volatility Display Logic
        vol_source = o.get("vol_source", "proxy_hv20")
        vol_title = "波动率"
        vol_footer = ""
        vol_help = ""
        
        if vol_source == "real_iv":
            vol_title = "隐含波动率 IV (ATM 30D)"
            vol_help = "期权市场预期的未来 30 天年化波动率。反映市场对未来价格波动的恐慌或贪婪程度。"
        else:
            vol_title = "历史波动率 (HV20, 代理 IV)"
            vol_help = "过去 20 个交易日的年化历史波动率 (Realized Vol)。<br>当期权数据不可用时，以此作为市场热度的代理指标。<br>数值越高，近期价格波动越剧烈。"
            vol_footer = '<div style="font-size:0.6rem; color:#475569; margin-top:8px; font-style:italic;">* 当前未接入期权隐含波，使用过去 20 个交易日年化历史波动率作为代理。</div>'

        st.markdown(f"""
        <div style="background:rgba(30, 41, 59, 0.3); border:1px solid rgba(255,255,255,0.05); border-radius:12px; padding:20px; min-height:160px;">
            <div style="font-size:0.75rem; color:#64748b; text-transform:uppercase; font-weight:700; margin-bottom:12px;">关键指标 (Key Metrics)</div>
            {_fmt_fact(vol_title, f"{iv_pct:.2f}", "%", help_text=vol_help)}
            {_fmt_fact("当日涨跌", f"{daily_ret*100:+.2f}", "%")}
            {_fmt_fact("当日量比 (vs MA20)", f"{vol_ratio:.1f}", "x", help_text="当日成交量与过去 20 日平均成交量的比值。<br>• >1.5x: 放量<br>• <0.6x: 缩量<br>放量通常意味着分歧或趋势的开始。")}
            {_fmt_fact("收盘位置", f"{cp*100:.0f}", "%", help_text="当日收盘价在当日最高价与最低价之间的相对位置。<br>• 100%: 收在最高 (极强)<br>• 0%: 收在最低 (极弱)<br>• 50%: 收在中间 (平衡)")}
            {vol_footer}
        </div>
        """, unsafe_allow_html=True)

    st.markdown('<div style="height:24px;"></div>', unsafe_allow_html=True)

    # --- ROW 2: Regime & Unlock Conditions ---
    st.markdown('<div style="font-size:0.95rem; font-weight:700; color:#e2e8f0; margin-bottom:12px;">价格结构 & 解锁条件 (Regime & Reasoning)</div>', unsafe_allow_html=True)
    c3, c4 = st.columns([2, 1], gap="medium")
    
    with c3:
        # Regime Desc
        u_def = get_u_state_def(u_state)
        st.markdown(f"""
        <div style="background:rgba(255,255,255,0.02); border:1px solid rgba(255,255,255,0.05); border-radius:12px; padding:20px; min-height:140px;">
            <div style="font-size:0.75rem; color:#64748b; text-transform:uppercase; margin-bottom:4px;">{u_state}</div>
            <div style="font-size:1.1rem; font-weight:700; color:#e2e8f0; margin-bottom:8px;">{u_label}</div>
            <div style="font-size:0.9rem; color:#94a3b8; line-height:1.6;">{u_def}</div>
        </div>
        """, unsafe_allow_html=True)

    with c4:
        # Unlock Conditions List
        next_conditions = d.get("next_conditions_details", [])
        nc_rows = ""
        expert_mode = st.session_state.get("expert_mode_active", False)
        
        if next_conditions:
            for cond in next_conditions:
                icon = cond.get("status", "❓")
                is_done = (icon == "✅")
                color = "#22c55e" if is_done else "#64748b"
                
                # Base row
                nc_rows += f'<div style="font-size:0.85rem; color:{color}; margin-bottom:4px; font-weight:600;">{icon} {cond.get("label")}</div>'
                
                # Expert details
                if expert_mode:
                    val = cond.get("value", "-")
                    tgt = cond.get("target", "-")
                    evi = cond.get("evidence", "")
                    detail_color = "#4ade80" if is_done else "#94a3b8"
                    nc_rows += f'<div style="font-size:0.75rem; color:{detail_color}; margin-left:24px; margin-bottom:10px; padding:4px 8px; background:rgba(255,255,255,0.03); border-radius:4px; border-left:2px solid {color}88;">'
                    nc_rows += f'<span style="opacity:0.7;">当前:</span> <b>{val}</b> '
                    nc_rows += f'<span style="opacity:0.7; margin-left:8px;">目标:</span> <b>{tgt}</b><br/>'
                    nc_rows += f'<span style="opacity:0.5; font-style:italic;">证据: {evi}</span>'
                    nc_rows += '</div>'
        else:
            nc_rows = '<div style="font-size:0.85rem; color:#64748b;">当前状态暂无特定解锁条件。</div>'

        st.markdown(
            f'<div style="background:rgba(255,255,255,0.02); border:1px solid rgba(255,255,255,0.05); border-radius:12px; padding:20px; min-height:140px;">'
            f'<div style="font-size:0.75rem; color:#64748b; text-transform:uppercase; font-weight:700; margin-bottom:12px;">解锁条件 (Unlock Conditions)</div>'
            f'{nc_rows}'
            f'<div style="font-size:0.65rem; color:#475569; margin-top:10px; font-style:italic;">* 条件达成前，PermissionEngine 将默认保持当前状态。</div>'
            f'</div>',
            unsafe_allow_html=True
        )

    st.markdown('<div style="height:24px;"></div>', unsafe_allow_html=True)

    # --- ROW 3: Action Gate ---
    st.markdown('<div style="font-size:0.95rem; font-weight:700; color:#e2e8f0; margin-bottom:12px;">行为权限 (Action Gate)</div>', unsafe_allow_html=True)
    a1, a2, a3 = st.columns(3, gap="medium")
    
    actions = d.get("allowed_actions", {})
    reasons = d.get("action_reasons", {})

    def _render_action_btn(col, key, label, icon="radar"):
        is_allowed = actions.get(key, False)
        reason = reasons.get(key, "禁止")
        
        # V2 状态逻辑划分
        if is_allowed:
            # 1. 🟢 可操作 (Actionable)
            color_theme = "#22c55e" # 鲜绿色
            bg = "rgba(34, 197, 94, 0.2)"
            status_text = reason if reason != "允许" else "允许执行"
            sym = "check_circle"
            box_glow = "0 4px 12px rgba(34, 197, 94, 0.15)"
        elif "待" in reason or "观察" in reason:
            # 2. ⚪ 观察期 (Observation)
            color_theme = "#f8fafc" # 亮白色/冰蓝色
            bg = "rgba(255, 255, 255, 0.08)"
            status_text = reason
            sym = "visibility"
            box_glow = "none"
        else:
            # 3. 🔴 否决/禁止 (Veto)
            color_theme = "#ef4444" # 鲜红色
            bg = "rgba(239, 68, 68, 0.12)"
            status_text = reason
            sym = "block"
            box_glow = "none"

        col.markdown(f"""
        <div style="background:{bg}; border-left:4px solid {color_theme}; border-radius:10px; padding:18px 16px; display:flex; align-items:center; justify-content:space-between; box-shadow:{box_glow}; min-height:80px;">
            <div style="display:flex; align-items:center; gap:12px;">
                <span class="material-symbols-outlined" style="font-size:22px; color:{color_theme}; opacity:0.8;">{sym}</span>
                <span style="font-size:1.05rem; font-weight:700; color:#cbd5e1;">{label}</span>
            </div>
            <div style="text-align:right;">
                <div style="font-size:1.15rem; font-weight:900; color:{color_theme}; letter-spacing:0.5px; text-transform:uppercase;">{status_text}</div>
                <div style="font-size:0.65rem; color:#64748b; margin-top:2px; font-weight:600; opacity:0.6;">ACTION SUGGESTION</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    _render_action_btn(a1, "buy_underlying", "买入标的")
    _render_action_btn(a2, "sell_put_csp", "卖出 Put (CSP)")
    _render_action_btn(a3, "roll_put", "期权滚动 (Roll)")

    st.markdown('<div style="font-size:0.7rem; color:#475569; margin-top:12px; text-align:right;">行为权限由 PermissionEngine 输出，前端不二次判断。</div>', unsafe_allow_html=True)


# Custom CSS for "Premium" feel
st.markdown("""
<style>
    /* 1. Global Layout: Wide Mode Enforcer */
    .stApp [data-testid="block-container"]{
        max-width: none !important;
        padding-left: 3rem !important;
        padding-right: 3rem !important;
    }
    
    /* Increase horizontal gap between columns */
    [data-testid="stHorizontalBlock"]{
        gap: 4rem !important;
        flex-wrap: nowrap !important;
        display: flex !important;
    }
    
    /* Global: Force ALL Streamlit columns to take equal width and not wrap */
    [data-testid="stColumn"] {
        min-width: 0 !important;
        flex: 1 1 0% !important;
        max-width: none !important;
    }

    /* 2. Section Titles & Dividers */
    .vera-section-title{
        font-size: 1.05rem;
        font-weight: 700;
        margin: 8px 0 12px 0;
        color: #e5e7eb;
    }
    .vera-divider{
        margin: 18px 0 14px 0;
        border-bottom: none;
    }
    
    /* 3. Verdict Box (Footer) */
    .vera-verdict{
        border: 1px solid rgba(255, 75, 75, 0.35);
        border-radius: 12px;
        padding: 16px 18px;
        background: rgba(255,75,75,0.06);
        color: #fca5a5;
        font-size: 1.1rem;
        font-weight: 600;
        text-align: left;
        margin-top: 10px;
    }

    /* 4. Risk Overlay Styles (Enhanced for V2.0) */
    /* Wrapper to force non-wrapping row */
    .vera-overlay-row [data-testid="stHorizontalBlock"] {
        flex-wrap: nowrap !important;
        gap: 1.5rem !important;
        display: flex !important;
        align-items: stretch !important; /* Ensure equal height columns */
    }
    
    /* Force each column to take equal width and prevent wrapping */
    .vera-overlay-row [data-testid="column"] {
        min-width: 0 !important;
        flex: 1 1 0 !important;
        max-width: none !important;
        display: flex !important;
        flex-direction: column !important;
    }
    
    .vera-overlay-col {
        background: rgba(255,255,255,0.02);
        border: 1px solid rgba(255,255,255,0.07);
        border-radius: 14px;
        padding: 14px 14px 8px 14px;
        height: 100%; /* Force equal height */
        display: flex;
        flex-direction: column;
        min-width: 0; /* Allow shrinking */
    }
    
    /* Grid container for metrics within each column */
    .vera-overlay-grid {
        flex: 1; /* Takes up remaining space */
        display: flex;
        flex-direction: column;
        gap: 8px;
    }
    
    .vera-overlay-header{
        display:flex;
        align-items:center;
        justify-content:space-between;
        padding: 0 0 12px 0;
        margin-bottom: 4px;
        border-bottom: none;
        border-radius: 0;
        background: transparent;
        border-top: none;
        border-left: none;
        border-right: none;
        margin-bottom: 12px;
        flex-shrink: 0; /* Prevent header from shrinking */
    }
    
    .vera-overlay-title{
        font-weight: 700;
        font-size: 1.35rem; 
        color: #e5e7eb;
    }
    
    .vera-overlay-sub{
        font-size: 0.85rem;
        color: #9ca3af;
        opacity: 0.95;
    }
    
    .vera-overlay-grid {
        flex: 1; /* Pushes footer down */
    }

    .vera-overlay-footer{
        margin-top: 10px;
        padding-top: 10px;
        border-top: none;
        font-size: 0.8rem;
        color: #9ca3af;
    }

    .vera-layer-label {
        font-size: 0.75rem;
        color: #ff4b4b;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 8px;
    }

    /* 5. Metrics & Cards */
    .vera-metric-card {
        background-color: transparent;
        border: none;
        padding: 0;
        margin-bottom: 0;
        position: relative;
    }
    .vera-metric-label {
        font-size: 13px;
        color: #9ca3af;
        margin-bottom: 6px;
        display: flex;
        align-items: center;
        gap: 6px;
    }
    .vera-metric-value {
        font-size: 24px;
        font-weight: 600;
        color: #ffffff;
        font-family: 'SF Pro Display', -apple-system, sans-serif;
    }
    
    /* 6. Behavior Flags & Quadrant */
    .behavior-flag {
        padding: 12px;
        border-radius: 8px;
        margin-bottom: 10px;
        border-left: 4px solid #ccc;
        background-color: #262626;
    }
    .flag-alert { border-left-color: #ff4b4b; background-color: rgba(255, 75, 75, 0.1); }
    .flag-warn { border-left-color: #ffa500; background-color: rgba(255, 165, 0, 0.1); }
    .flag-info { border-left-color: #2e7d32; background-color: rgba(46, 125, 50, 0.1); }
    
    .risk-matrix-container {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 8px; /* Slightly more spacing */
        max-width: 100%;
        position: relative;
    }
    .risk-matrix-cell {
        display: flex;
        flex-direction: column; /* Force vertical stack */
        align-items: center;
        justify-content: center;
        border: 1px dashed rgba(255, 255, 255, 0.15); /* Reference-style dashed border */
        border-radius: 8px; /* Slightly more rounded */
        padding: 12px;
        color: rgba(255, 255, 255, 0.3); /* Dimmer inactive text */
        font-size: 0.85rem;
        line-height: 1.3; /* Adjusted for two lines */
        text-align: center;
        transition: all 0.4s cubic-bezier(0.165, 0.84, 0.44, 1);
        background: transparent;
    }
    .cell-active {
        background: #ff4b4b; /* Solid base color for reference match */
        color: white !important;
        border: none !important;
        font-weight: 700;
        box-shadow: 0 0 20px rgba(255, 75, 75, 0.5), 0 0 40px rgba(255, 75, 75, 0.2); /* Dual-layer glow */
        transform: scale(1.02); /* Subtle pop-out effect */
        z-index: 2;
    }
    /* Cell labels specific to reference image nomenclature */
    .risk-matrix-cell-q2.cell-active { background: #ff4b4b; box-shadow: 0 0 25px rgba(255, 75, 75, 0.6); } /* Bubble/Red */
    .risk-matrix-cell-q1.cell-active { background: #3b82f6; box-shadow: 0 0 25px rgba(59, 130, 246, 0.6); } /* Following/Blue */
    .risk-matrix-cell-q4.cell-active { background: #10b981; box-shadow: 0 0 25px rgba(16, 185, 129, 0.6); } /* Stable/Green */
    .risk-matrix-cell-q3.cell-active { background: #f59e0b; box-shadow: 0 0 25px rgba(245, 158, 11, 0.6); } /* Panic/Yellow */

    /* Tooltip System */
    .vera-help-icon {
        display: inline-block;
        margin-left: 6px;
        opacity: 0.4;
        font-size: 14px;
        cursor: help;
        transition: opacity 0.2s;
        vertical-align: middle;
    }
    .vera-help-icon:hover {
        opacity: 1.0;
        color: #ff4b4b;
    }

    .vera-tooltip {
        position: relative;
        cursor: help;
        border-bottom: 1px dotted #666;
    }
    
    /* Sticky Header Logic */
    div[data-testid="element-container"]:has(#vera-sticky-anchor) {
        position: sticky;
        top: 60px;
        z-index: 999;
    }

    /* Standardized Metric Card & Tooltip */

    .vera-metric-label {
        font-size: 13px;
        color: #9ca3af;
        margin-bottom: 6px;
        display: flex;
        align-items: center;
        gap: 6px;
        font-family: -apple-system, BlinkMacSystemFont, sans-serif;
    }
    .vera-metric-value {
        font-size: 24px;
        font-weight: 600;
        color: #ffffff;
        line-height: 1.2;
        font-family: 'SF Pro Display', -apple-system, sans-serif;
    }
    /* Fixed overlay bottom-right */
    /* Fixed overlay removed - using relative absolute positioning instead */

    .vera-metric-card:hover .metric-help-overlay,
    .vera-tooltip-trigger:hover .metric-help-overlay {
        display: block;
    }
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }


    div[data-testid="element-container"]:has(#vera-sticky-anchor) + div[data-testid="element-container"] {
        position: sticky;
        top: 60px;
        background-color: #0e1117;
        z-index: 998;
        padding-top: 10px;
        border-bottom: 1px solid rgba(255, 75, 75, 0.3);
    }
    
    /* Inline Metrics Helpers */
    .inline-metric-container { margin-bottom: 2px; }
    .inline-metric-delta {
        font-size: 0.85rem;
        font-weight: 600;
        padding: 1px 5px;
        border-radius: 4px;
        margin-left: 6px;
    }
    .delta-up { background-color: rgba(255, 75, 75, 0.1); color: #ff4b4b; }
    .delta-down { background-color: rgba(40, 167, 69, 0.1); color: #28a745; }
    .delta-neutral { background-color: rgba(100, 100, 100, 0.1); color: #888; }
    .inline-metric-details { font-size: 0.75rem; color: #666; margin-left: 6px; }

</style>
""", unsafe_allow_html=True)

def render_inline_metric(label, value, delta=None, delta_color="normal", help_text="", details=""):
    """统一渲染指标块"""
    delta_html = ""
    if delta:
        d_class = "delta-neutral"
        if delta_color == "normal":
            d_class = "delta-up" if "+" in delta or any(c.isdigit() for c in delta) else "delta-down"
        elif delta_color == "inverse":
            d_class = "delta-down" if "+" in delta or any(c.isdigit() for c in delta) else "delta-up"
        elif delta_color == "off":
            d_class = "delta-neutral"
        
        # 兼容百分比分位显示
        if "th" in delta:
            d_class = "delta-up" if float(delta.replace("th", "")) > 80 else "delta-neutral"

        delta_html = f'<span class="inline-metric-delta {d_class}">{delta}</span>'
    
    details_html = f'<span class="inline-metric-details">{details}</span>' if details else ""
    
    
    # CSS Style Definition

    
    # Tooltip logic: Restore "onmouse" overlay effect
    # The overlay is hidden by default and shown on .vera-metric-card:hover (handled by CSS)
    tooltip_attr = "" 
    cursor_style = 'cursor: default;' if help_text else ''
    
    # Help Overlay HTML (Relative to term)
    help_html = ""
    if help_text:
        help_html = f'<div class="metric-help-overlay">{help_text}</div><span class="vera-help-icon">ⓘ</span>'
    
    html = f"""
<div class="vera-metric-card" style="{cursor_style}" {tooltip_attr}>
<div class="vera-metric-label vera-tooltip-trigger">
{label} {help_html}
</div>
<div class="vera-metric-value">{value}</div>
{delta_html}
{details_html}
</div>
"""
    st.markdown(html, unsafe_allow_html=True)

def render_risk_matrix(quadrant):
    """渲染 2x2 风险象限矩阵"""
    cells = {
        "Q1": "Q1 追涨区",
        "Q2": "Q2 泡沫区",
        "Q3": "Q3 恐慌区",
        "Q4": "Q4 稳态区"
    }
    
    # 映射象限到 grid 位置 (Streamlit grid 是 Row-major)
    # Q2 | Q1
    # ---+---
    # Q3 | Q4
    order = ["Q2", "Q1", "Q3", "Q4"]
    
    st.markdown('<h5 style="margin-bottom: 20px;">📍 位置/行为风险 (Position Risk)</h5>', unsafe_allow_html=True)
    html = '<div class="risk-matrix-container">'
    for q in order:
        active_class = "cell-active" if q == quadrant else ""
        html += f'<div class="risk-matrix-cell {active_class}">{cells[q]}</div>'
    
    html += '<div class="matrix-axis-label y-axis-label">价格路径风险 (Path Risk) →</div>'
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)

def render_behavior_flags(flags):
    """渲染行为护栏卡片"""
    if not flags: return
    
    st.markdown('<h5 style="margin-bottom: 20px;">🧱 行为护栏 (Behavior Flags)</h5>', unsafe_allow_html=True)
    for f in flags:
        level_class = f"flag-{f['flag_level'].lower()}"
        icon = "🚨" if f['flag_level'] == "ALERT" else "⚠️" if f['flag_level'] == "WARN" else "ℹ️"
        
        st.markdown(f"""
        <div class="behavior-flag {level_class}">
            <div style="font-weight: bold; color: #333; margin-bottom: 5px;">{icon} {f['flag_title']}</div>
            <div style="font-size: 0.9rem; color: #666;">{f['flag_description']}</div>
        </div>
        """, unsafe_allow_html=True)

def render_conclusion_badge(conclusion: str):
    # Split "Conclusion (Reason)" into two parts
    parts = conclusion.split(" (")
    main_text = parts[0]
    sub_text = parts[1].replace(")", "") if len(parts) > 1 else ""
    
    html_content = f"{main_text}"
    if sub_text:
        html_content += f"<br><span style='font-size: 0.65em; font-weight: normal; opacity: 0.9;'>{sub_text}</span>"
        
    if "适合" in conclusion and "不适合" not in conclusion:
        return f'<div class="conclusion-badge-hold" style="display:inline-block; text-align:center;">{html_content}</div>'
    elif "不适合" in conclusion or "陷阱" in conclusion:
        return f'<div class="conclusion-badge-avoid" style="display:inline-block; text-align:center;">{html_content}</div>'
    else:
        return f'<div class="conclusion-badge-watch" style="display:inline-block; text-align:center;">{html_content}</div>'

def detect_risk_combination(data, profile: Optional[RiskProfile] = None):
    """
    检测高风险组合
    返回: (风险等级, 警示信息) 或 None
    """
    if not data.path or not data.path.get('state'):
        return None
    
    state = data.path['state']
    volatility = data.volatility
    
    # 获取画像偏好 (如果没有 profile，默认为 BALANCED)
    verbosity = profile.warning_verbosity if profile else "STANDARD"
    
    # 进取型视角：调高敏感阈值
    if profile and profile.risk_tolerance_level == RiskProfile.LEVEL_AGGRESSIVE:
        if state == "D0" and volatility > 0.60:
            return ("极高", "⚠️ 极端高位波动 (进取型提醒)", "价格处于历史高点且波动率极高，面临由于杠杆连环爆仓导致的非线性下跌风险。")
        return None # 进取型忽略普通高波动

    # 高风险组合检测
    # 1. D0 + 高波动
    vol_threshold = 0.50
    if profile and profile.risk_tolerance_level == RiskProfile.LEVEL_CONSERVATIVE:
        vol_threshold = 0.40
    
    if state == "D0" and volatility > vol_threshold:
        msg = f"当前处于历史高位（{state}），但年化波动率高达 {volatility*100:.1f}%，存在快速回撤风险。"
        if verbosity == "DETAILED":
            msg += " 保守型投资者应警惕高位筹码松动及潜在的‘流动性陷阱’，建议关注下行确认期。"
        return ("极高" if volatility > 0.50 else "高", "⚠️ 高位高波动组合", msg)
    
    # 2. D4 + 高波动
    if state == "D4" and volatility > 0.30:
        return ("极高", "🚨 二次探底风险", 
                f"当前处于反弹早期（{state}），且波动率 {volatility*100:.1f}% 较高，这是最容易发生二次探底的阶段。")
    
    # 3. D3 + 高波动
    if state == "D3" and volatility > 0.40:
        return ("极高", "💥 极度脆弱区域", 
                f"处于深度回撤区域（{state}），波动率 {volatility*100:.1f}% 极大，暗示市场分歧剧烈且恐慌情绪未定。")
    
    # 5. D5 + 高波动：修复失败风险
    if state == "D5" and volatility > 0.35:
        return ("中", "🔄 修复不稳定", 
                f"当前处于修复中段（{state}），但波动率 {volatility*100:.1f}% 仍然较高，存在修复失败回落至 D2 的风险。")
    
    return None

def get_cached_symbols():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT asset_id FROM asset_universe WHERE is_active = 1 ORDER BY asset_id")
        raw_symbols = [row[0] for row in cursor.fetchall()]
        conn.close()
        return sorted(list(set(raw_symbols)))
    except:
        return []

def get_asset_evaluation_history(asset_id: str):
    """获取指定资产的所有历史评估记录"""
    try:
        from utils.canonical_resolver import resolve_canonical_symbol
        
        conn = get_connection()
        
        # Convert simplified code to Canonical ID if needed
        # If asset_id doesn't contain ':', it's likely a simplified code
        if ':' not in asset_id:
            try:
                canonical_id = resolve_canonical_symbol(
                    conn, 
                    asset_id,
                    strict_unknown=False  # Don't raise error if not found
                )
            except Exception:
                # If resolution fails, use the original asset_id
                canonical_id = asset_id
        else:
            canonical_id = asset_id
        
        query = """
        SELECT 
            s.snapshot_id,
            s.asset_id,
            s.as_of_date,
            s.created_at,
            s.valuation_status,
            s.risk_level,
            a.name as symbol_name
        FROM analysis_snapshot s
        JOIN assets a ON s.asset_id = a.asset_id
        WHERE s.asset_id = ?
        ORDER BY s.created_at DESC
        """
        df = pd.read_sql_query(query, conn, params=(canonical_id,))
        conn.close()
        return df
    except Exception as e:
        st.error(f"获取历史记录失败: {str(e)}")
        return pd.DataFrame()

def get_evaluation_history(show_all=False):
    """获取评估记录。show_all=True 时返回所有记录，False 时返回每资产最新记录"""
    try:
        conn = get_connection()
        if show_all:
            query = """
            SELECT 
                s.snapshot_id, s.asset_id, s.as_of_date, s.created_at,
                s.valuation_status, s.risk_level, a.name as symbol_name
            FROM analysis_snapshot s
            JOIN assets a ON s.asset_id = a.asset_id
            ORDER BY s.created_at DESC
            """
        else:
            # 使用窗口函数获取每个资产的最新记录
            query = """
            WITH latest_snapshots AS (
                SELECT 
                    s.snapshot_id, s.asset_id, s.as_of_date, s.created_at,
                    s.valuation_status, s.risk_level, a.name as symbol_name,
                    ROW_NUMBER() OVER (PARTITION BY s.asset_id ORDER BY s.created_at DESC) as rn
                FROM analysis_snapshot s
                JOIN assets a ON s.asset_id = a.asset_id
            )
            SELECT snapshot_id, asset_id, symbol_name, as_of_date, created_at, valuation_status, risk_level
            FROM latest_snapshots
            WHERE rn = 1
            ORDER BY created_at DESC
            """
        df = pd.read_sql(query, conn)
        conn.close()
        return df
    except Exception as e:
        st.error(f"获取历史记录失败: {str(e)}")
        return pd.DataFrame()

def delete_all_evaluation_history():
    """清空所有评估历史记录"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        
        # 手动清理没有级联删除的关联表
        for tb in ["risk_overlay_snapshot", "sector_risk_snapshot", "quality_snapshot", "quality_snapshot_old"]:
            try:
                cursor.execute(f"DELETE FROM {tb}")
            except:
                pass
        
        # 清理主表 (级联删除会自动处理大部分关联表: metric_details, risk_card_snapshot, behavior_flags, decision_log)
        cursor.execute("DELETE FROM analysis_snapshot")
        
        conn.commit()
        conn.close()
        
        log_path = "/Users/zhangzy/My Docs/Privates/22-AI编程/VERA/delete_debug.log"
        with open(log_path, "a") as f:
            f.write(f"{datetime.now()}: ALL History cleared successfully\n")
            
        return True, "所有历史记录已清除"
    except Exception as e:
        log_path = "/Users/zhangzy/My Docs/Privates/22-AI编程/VERA/delete_debug.log"
        with open(log_path, "a") as f:
            f.write(f"{datetime.now()}: Error clearing ALL history: {str(e)}\n")
        return False, str(e)

def delete_asset_evaluation_history(asset_id: str):
    """删除特定资产的所有评估历史记录"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        
        # 获取所有相关的 snapshot_id
        cursor.execute("SELECT snapshot_id FROM analysis_snapshot WHERE asset_id = ?", (asset_id,))
        sids = [row[0] for row in cursor.fetchall()]
        
        if not sids:
            conn.close()
            return True, "无记录需删除"
            
        placeholders = ','.join(['?'] * len(sids))
        
        # 手动清理无级联的表
        for tb in ["risk_overlay_snapshot", "sector_risk_snapshot", "quality_snapshot", "quality_snapshot_old"]:
            try:
                cursor.execute(f"DELETE FROM {tb} WHERE snapshot_id IN ({placeholders})", sids)
            except:
                pass
        
        # 清理主表
        cursor.execute("DELETE FROM analysis_snapshot WHERE asset_id = ?", (asset_id,))
        
        conn.commit()
        conn.close()
        return True, f"成功删除 {len(sids)} 条记录"
    except Exception as e:
        return False, str(e)

def delete_snapshot(snapshot_id: str):
    """删除指定的评估快照"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        
        # 手动清理没有级联删除的关联表
        # 注意：有些表可能没有该 snapshot_id，DELETE 不会报错
        for tb in ["risk_overlay_snapshot", "sector_risk_snapshot", "quality_snapshot", "quality_snapshot_old"]:
            try:
                cursor.execute(f"DELETE FROM {tb} WHERE snapshot_id = ?", (snapshot_id,))
            except:
                pass
        
        # 清理主表
        cursor.execute("DELETE FROM analysis_snapshot WHERE snapshot_id = ?", (snapshot_id,))
        
        log_path = "/Users/zhangzy/My Docs/Privates/22-AI编程/VERA/delete_debug.log"
        if cursor.rowcount == 0:
            conn.close()
            with open(log_path, "a") as f:
                f.write(f"{datetime.now()}: Snapshot {snapshot_id} not found for deletion\n")
            return False, "未找到目标记录"
            
        conn.commit()
        conn.close()
        with open(log_path, "a") as f:
            f.write(f"{datetime.now()}: Snapshot {snapshot_id} deleted successfully\n")
        return True, "删除成功"
    except Exception as e:
        log_path = "/Users/zhangzy/My Docs/Privates/22-AI编程/VERA/delete_debug.log"
        with open(log_path, "a") as f:
            f.write(f"{datetime.now()}: Error deleting {snapshot_id}: {str(e)}\n")
        return False, str(e)

def get_snapshot_details(snapshot_id: str):
    """获取单个快照的完整详情"""
    try:
        conn = get_connection()
        
        # 1. 基础信息
        snapshot_query = """
            SELECT s.*, a.name as symbol_name, a.market, a.asset_type as category
            FROM analysis_snapshot s
            JOIN assets a ON s.asset_id = a.asset_id
            WHERE s.snapshot_id = ?
        """
        snapshot_df = pd.read_sql(snapshot_query, conn, params=(snapshot_id,))
        
        # 2. 指标详情
        metrics_query = "SELECT * FROM metric_details WHERE snapshot_id = ?"
        metrics_df = pd.read_sql(metrics_query, conn, params=(snapshot_id,))
        
        # 3. 风险卡片
        risk_card_query = "SELECT * FROM risk_card_snapshot WHERE snapshot_id = ?"
        risk_card_df = pd.read_sql(risk_card_query, conn, params=(snapshot_id,))
        
        # 4. 行为标志
        behavior_query = "SELECT * FROM behavior_flags WHERE snapshot_id = ?"
        behavior_df = pd.read_sql(behavior_query, conn, params=(snapshot_id,))
        
        # 5. 质量快照
        quality_query = "SELECT * FROM quality_snapshot WHERE snapshot_id = ?"
        quality_df = pd.read_sql(quality_query, conn, params=(snapshot_id,))
        
        # 6. 风险叠加
        overlay_query = "SELECT * FROM risk_overlay_snapshot WHERE snapshot_id = ?"
        overlay_df = pd.read_sql(overlay_query, conn, params=(snapshot_id,))
        
        # 7. 决策日志
        decision_query = "SELECT * FROM decision_log WHERE snapshot_id = ?"
        decision_df = pd.read_sql(decision_query, conn, params=(snapshot_id,))
        
        conn.close()
        
        return {
            'snapshot': snapshot_df,
            'metrics': metrics_df,
            'risk_card': risk_card_df,
            'behavior': behavior_df,
            'quality': quality_df,
            'overlay': overlay_df,
            'decision': decision_df
        }
    except Exception as e:
        st.error(f"获取快照详情失败: {str(e)}")
        return None

def extract_data_from_image(uploaded_file):
    """
    模拟 OCR 解析逻辑
    真实场景下会调用 GPT-4V 或 Text-in API
    此处针对演示图片做特定的解析模拟
    """
    filename = uploaded_file.name
    
    # Defaults
    data = {
        "symbol": "",
        "price": 0.0,
        "change_percent": 0.0,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "pe_ttm": None
    }
    
    # 模拟解析逻辑 (基于用户提供的图片特征)
    if "TSLA" in filename or "0" in filename: # Assuming 0 is the first uploaded image
        data = {
            "symbol": "TSLA",
            "price": 488.730,
            "change_percent": 1.56,
            "date": "2025-12-23", # Set to today for demo
            "pe_ttm": 337.06
        }
    elif "MSFT" in filename or "1" in filename:
        data = {
            "symbol": "MSFT",
            "price": 484.920,
            "change_percent": -0.21,
            "date": "2025-12-23",
            "pe_ttm": 34.49
        }
    else:
        # Fallback random mock for other files
        data["symbol"] = "UNKNOWN"
    
    return data


# ---------------------------
# VERA V2.0 UI Components
# ---------------------------

def section_title(text: str):
    st.markdown(f'<div class="vera-section-title">{text}</div>', unsafe_allow_html=True)

def divider():
    st.markdown('<div class="vera-divider"></div>', unsafe_allow_html=True)

# --- Helper for HTML Rendering ---
def clean_html(html_str):
    """Flattens HTML string to avoid Markdown code block interpretation."""
    import re
    return re.sub(r'^\s+', '', html_str, flags=re.MULTILINE).replace('\n', '')

def render_header(data: DashboardData, is_index: bool = False, index_role: str = None, expert_mode: bool = False):
    """【资产标题 + 基本信息】Styled Header"""
    
    # 1. Navigation / Actions Toolbar
    c1, c2, c3, c4 = st.columns([1.2, 5, 1.2, 1.2])
    
    def _shift_date(days):
        st.session_state.eval_date = st.session_state.eval_date + timedelta(days=days)

    def _save_record():
        try:
            # 优先使用 asset_id 确保精确性 (例如 HK:STOCK:00700)
            target_id = data.symbol
            if hasattr(data, 'asset_id') and data.asset_id:
                target_id = data.asset_id
                
            run_snapshot(target_id, as_of_date=st.session_state.eval_date, save_to_db=True)
            st.session_state.last_save_status = ("success", f"✅ 已成功保存 {data.symbol_name} ({target_id}) 的分析记录！")
        except Exception as e:
            st.session_state.last_save_status = ("error", f"❌ 保存失败: {str(e)}")

    with c1:
        st.button("⬅️ 前一天", key="btn_prev_day", on_click=_shift_date, args=(-1,))
    with c3:
        st.button("💾 保存记录", key="btn_save", on_click=_save_record, help="将当前分析结果永久保存到数据库历史记录中")
    with c4:
        st.button("后一天 ➡️", key="btn_next_day", on_click=_shift_date, args=(1,))
        
    # 2. Asset Info Header (HTML)
    # Market Logic
    sym = data.symbol.upper()
    if sym.startswith("HK:") or sym.endswith(".HK") or sym in ["HSI", "HSTECH", "HSCE"]:
        market_region = "HK (港股)"
    elif sym.startswith("CN:") or sym.endswith(".SS") or sym.endswith(".SZ") or sym == "000300" or (sym.isdigit() and len(sym)==6): 
        market_region = "CN (A股)"
    else:
        market_region = "US (美股)"

    # Type Logic
    if is_index:
        type_str = f"Index ({index_role or 'Index'})"
    else:
        type_str = "Stock (个股)" 
        
    # Asset Info Section
    # NOTE: formatted flush-left
    # change logic
    chg = data.change_percent or 0.0
    c_color = "#ef4444" if chg < 0 else "#22c55e"
    sign = "+" if chg > 0 else ""
    
    expert_badge = ""
    if expert_mode:
        expert_badge = '<span style="background:#3b82f6; color:white; padding:4px 10px; border-radius:12px; font-size:0.75rem; font-weight:700; margin-left:12px; vertical-align:middle;">🔬 EXPERT AUDIT MODE ON</span>'

    html = f"""
<section style="display:grid; grid-template-columns: 2fr 1fr 1fr; gap:32px; align-items:flex-end; margin: 20px 0 32px 0;">
    <div>
        <h2 style="font-size:2rem; font-weight:700; color:#fff; margin-bottom:8px;">{data.symbol_name} ({data.symbol}) {expert_badge}</h2>
        <div style="display:flex; align-items:baseline; margin-top:8px;">
            <span style="font-size:2.5rem; font-weight:700; color:#f1f5f9;">{data.price:,.2f}</span>
            <span style="font-size:1.1rem; margin-left:12px; font-weight:500; color:{c_color};">{sign}{chg:.2f}%</span>
            <span style="margin-left:16px; font-size:0.9rem; color:#94a3b8;">{data.report_date}</span>
        </div>
    </div>
    <div>
        <p style="font-size:0.75rem; font-weight:600; color:#64748b; text-transform:uppercase; letter-spacing:0.05em; margin-bottom:4px;">资产类型</p>
        <p style="font-size:1.5rem; font-weight:500; color:#e2e8f0;">{type_str}</p>
    </div>
    <div>
        <p style="font-size:0.75rem; font-weight:600; color:#64748b; text-transform:uppercase; letter-spacing:0.05em; margin-bottom:4px;">市场</p>
        <p style="font-size:1.5rem; font-weight:500; color:#e2e8f0;">{market_region}</p>
    </div>
</section>
"""
    st.markdown(clean_html(html), unsafe_allow_html=True)


# --- Inline Components for Top Decision Area (B区) ---

def render_supplementary_card(data: DashboardData, profile: Optional[RiskProfile] = None, vera_result: dict = None):
    """
    Unified Supplementary Indicators Card (Replaces independent inline cards)
    """
    # 1. Prepare Matrix HTML (Position Risk)
    quadrant = data.risk_card.get('risk_quadrant', '') if data.risk_card else 'N/A'
    code = quadrant.split("_")[0] if "_" in quadrant else quadrant
    
    # Updated labels match reference image Image 0
    cells = [
        {"id": "Q3", "name": "恐慌", "class": "risk-matrix-cell-q3"}, 
        {"id": "Q2", "name": "泡沫", "class": "risk-matrix-cell-q2"},
        {"id": "Q4", "name": "稳态", "class": "risk-matrix-cell-q4"}, 
        {"id": "Q1", "name": "追涨", "class": "risk-matrix-cell-q1"}
    ]
    matrix_inner_html = '<div class="risk-matrix-container" style="height:100%; display:grid; grid-template-columns:1fr 1fr; gap:8px;">'
    for cell in cells:
        is_active = (code == cell["id"])
        base_cls = f"risk-matrix-cell {cell['class']}"
        cls = f"{base_cls} cell-active" if is_active else base_cls
        # Label split into 2 lines
        matrix_inner_html += f'<div class="{cls}"><span>{cell["id"]}</span><span>{cell["name"]}</span></div>'
    matrix_inner_html += '</div>'
    
    col1_html = f"""
    <div style="height:100%; display:flex; flex-direction:column; align-items:center;">
        <span style="font-weight:700; color:#e2e8f0; font-size:0.95rem; margin-bottom:24px; letter-spacing:0.02em;">位置风险 / 象限</span>
        <div style="position:relative; width:150px; height:150px;">
             <!-- Labels Positioning to match reference exactly -->
             <span style="position:absolute; top:-22px; left:50%; transform:translateX(-50%); font-size:0.65rem; color:#64748b; white-space:nowrap;">结构脆弱 (Fragile) ↑</span>
             <span style="position:absolute; bottom:-22px; left:50%; transform:translateX(-50%); font-size:0.65rem; color:#64748b; white-space:nowrap;">结构稳健 (Stable) ↓</span>
             <span style="position:absolute; top:50%; left:-32px; transform:translateY(-50%) rotate(-90deg); font-size:0.65rem; color:#64748b; white-space:nowrap;">← 低位</span>
             <span style="position:absolute; top:50%; right:-32px; transform:translateY(-50%) rotate(90deg); font-size:0.65rem; color:#64748b; white-space:nowrap;">高位 →</span>
             {matrix_inner_html}
        </div>
    </div>
    """

    # 2. Prepare Cognitive HTML
    msg = "信号不构成明显行动建议，<br>保持观望。"
    box_style = "background: rgba(59, 130, 246, 0.1); border: 1px solid rgba(59, 130, 246, 0.2); color: #93c5fd;"
    if profile and data.risk_card:
        if data.cognitive_warning and data.cognitive_warning != "正常风险范围":
             msg = data.cognitive_warning
             box_style = "background: rgba(245, 124, 0, 0.1); border: 1px solid #F57C00; color: #F57C00;"
    
    col2_html = f"""
    <div style="height:100%; display:flex; flex-direction:column;">
        <span style="font-weight:600; color:#e2e8f0; font-size:0.9rem; margin-bottom:16px;">认知预警 (Cognitive Alerts)</span>
        <div style="flex:1; width:100%; display:flex; align-items:center; justify-content:center; padding:20px; border-radius:8px; font-size:0.85rem; {box_style}">
             {msg}
        </div>
    </div>
    """

    # 3. Prepare Alerts HTML
    alerts_content = ""
    if vera_result and "decision" in vera_result and vera_result["decision"].get("evidence"):
         for item in vera_result["decision"]["evidence"]:
             alerts_content += f"""<div style="padding:8px 12px; margin-bottom:8px; background:rgba(0, 172, 193, 0.1); border-left:3px solid #00acc1; border-radius:4px;"><div style="font-size:0.8rem; color:#e0f7fa; font-weight:500;">{item}</div></div>"""
    else:
         flags = data.behavior_flags or []
         for flag in flags[:3]:
             level = flag.get('flag_level', 'INFO')
             color = {"ALERT": "#ef4444", "WARN": "#f97316", "INFO": "#3b82f6"}.get(level, "#64748b")
             alerts_content += f"""<div style="padding:8px 12px; margin-bottom:8px; background:rgba(255,255,255,0.03); border-left:3px solid {color}; border-radius:4px;"><div style="font-size:0.8rem; color:{color}; font-weight:500;">{flag.get('flag_title')}</div></div>"""
    
    if not alerts_content:
        alerts_content = """<div style="width:100%; height:100px; display:flex; align-items:center; justify-content:center; border:1px dashed #334155; border-radius:6px; color:#64748b; font-style:italic;">无执行告警</div>"""

    col3_html = f"""
    <div style="height:100%; display:flex; flex-direction:column;">
        <span style="font-weight:600; color:#e2e8f0; font-size:0.9rem; margin-bottom:16px;">执行告警 (Alerts)</span>
        <div style="flex:1; width:100%; overflow-y:auto; max-height:200px;">
             {alerts_content}
        </div>
    </div>
    """

    # 4. Combine into VERA Card
    # Use grid with 3 equal columns as requested
    html = f"""
    <div class="vera-card">
        <div class="vera-card-header">
            <span style="font-weight:700; color:#e2e8f0; font-size:0.9rem;">📊 辅助指标 (Supplementary Signals)</span>
        </div>
        <div class="vera-card-body" style="grid-template-columns: repeat(3, 1fr); gap: 32px;">
            <div style="padding-right:24px;">{col1_html}</div>
            <div style="padding:0 8px;">{col2_html}</div>
            <div style="padding-left:24px;">{col3_html}</div>
        </div>
    </div>
    """
    st.markdown(clean_html(html), unsafe_allow_html=True)


def render_quality_card(data: DashboardData):
    """4. 质量缓冲 (Quality Buffer) - Unified Card"""
    q = data.quality or {}
    
    # 1. Flag Translations & Help Texts
    flag_translations = {
        "STRONG": "强", "MID": "中", "WEAK": "弱", "LOW": "低", "HIGH": "高",
        "POSITIVE": "积极", "NEUTRAL": "中性", "NEGATIVE": "消极", "-": "-"
    }
    def translate_flag(value): return flag_translations.get(value, value)

    help_texts = {
        "revenue_stability": "收入稳定性：衡量过去3-5年营收增长的波动率。波动越小，评级越高。",
        "cyclicality": "周期性：基于行业属性和贝塔系数判断。弱周期性意味着业绩受宏观经济影响较小。",
        "moat": "护城河：基于毛利率水平和定价权。高毛利通常意味着拥有某种竞争壁垒。",
        "balance_sheet": "资产负债表：衡量负债率和流动性。负债越低、流动性越好，评级越高。",
        "cashflow_coverage": "现金流覆盖：经营性现金流对债务或利息的覆盖能力。覆盖倍数越高越安全。",
        "leverage_risk": "杠杆风险：基于净债务/EBITDA等指标。杠杆越低，财务风险越小。",
        "payout_consistency": "分红一致性：衡量过去分红记录的连续性和稳定性。连续分红通常是治理良好的标志。",
        "dilution_risk": "稀释风险：衡量股本扩张速度。股本增加越快，每股收益稀释风险越大。",
        "regulatory_dependence": "监管依赖：行业受政策干预的程度。依赖度越低，经营自主性越高。"
    }

    # 2. Build Components HTML
    
    # A. Top Buffer Status
    quality_level = q.get("quality_buffer_level", "Unknown")
    quality_summary = q.get("quality_summary", "暂无数据")
    
    q_colors = {"STRONG": "#2E7D32", "MODERATE": "#F57C00", "WEAK": "#C62828", "Unknown": "#9CA3AF"}
    q_color = q_colors.get(quality_level, "#9CA3AF")
    q_icon = {"STRONG": "🛡️", "MODERATE": "🌗", "WEAK": "⚠️", "Unknown": "❓"}.get(quality_level, "❓")
    
    html_status = f"""
<div style="background:{q_color}1a; border-left:4px solid {q_color}; padding:14px 18px; border-radius:4px; margin-bottom:24px;">
    <div style="font-size:1.1rem; font-weight:700; color:{q_color}; display:flex; align-items:center; margin-bottom:6px;">
            <span style="margin-right:8px;">{q_icon}</span> Quality Buffer: {translate(quality_level, "zh_only")}
            <span class="vera-help-icon" style="font-size:0.9rem; opacity:0.6;" title="基于财务、治理、业务三大维度综合评分">ⓘ</span>
    </div>
    <div style="color:#d1d5db; font-size:0.9rem; line-height:1.5;">{quality_summary}</div>
</div>
"""

    # B. Metrics (Dividend & Earnings)
    # Reusing get_metric_html logic (inline)
    
    # Dividend
    div_level = q.get("dividend_safety_level", "N/A")
    div_label = q.get("dividend_safety_label_zh", "-")
    div_notes = q.get("dividend_notes", [])
    div_desc = "，".join(div_notes) if div_notes else "暂无详细说明"
    d_color = {"STRONG":"#2E7D32", "MEDIUM":"#F57C00", "WEAK":"#C62828"}.get(div_level, "#9CA3AF")
    
    html_div = _get_metric_html_string(
        "分红安全性", 
        f'<span style="color:{d_color}">{div_label}</span>', 
        details=div_desc, 
        help_text=f"分红安全性评级: {div_level}<br>{div_desc}"
    )

    # Earnings
    e_label = q.get("earnings_state_label_zh", "-")
    e_code = q.get("earnings_state_code", "")
    e_desc = q.get("earnings_state_desc_zh", "暂无数据")
    e_color = "#9CA3AF"
    if e_code in ["E1", "E2", "E6"]: e_color = "#2E7D32" 
    elif e_code in ["E4", "E5"]: e_color = "#C62828"
    elif e_code in ["E3"]: e_color = "#F57C00"
    
    html_earn = _get_metric_html_string(
        "盈利周期状态", 
        f'<span style="color:{e_color}">{e_label} <small style="opacity:0.7;">{e_code}</small></span>',
        details=e_desc,
        help_text=f"当前处于盈利周期: {e_code}<br>{e_desc}"
    )

    # C. Flags Detail (HTML Table logic)
    def _build_flag_row(label, key, help_key):
        val = translate_flag(q.get(key, 'N/A'))
        tooltip = help_texts.get(help_key, "")
        color = "#9CA3AF"
        raw = q.get(key)
        if raw in ["LOW"] and key in ["leverage_risk_flag", "dilution_risk_flag", "regulatory_dependence_flag"]: color = "#4ade80"
        elif raw in ["HIGH"] and key in ["leverage_risk_flag", "dilution_risk_flag", "regulatory_dependence_flag"]: color = "#f87171"
        elif raw in ["STRONG", "POSITIVE", "HIGH"]: color = "#4ade80"
        elif raw in ["WEAK", "NEGATIVE"]: color = "#f87171"
        elif raw in ["MODERATE", "MID", "NEUTRAL"]: color = "#fbbf24"
        
        return f"""
        <div class="vera-compact-row" title="{tooltip}" style="display:flex; justify-content:space-between; padding:4px 0; border-bottom:1px dashed rgba(255,255,255,0.05);">
            <span style="color:#9ca3af;">{label}</span>
            <span style="color:{color}; font-weight:600;">{val}</span>
        </div>
        """

    col_biz = _build_flag_row("收入稳定性", 'revenue_stability_flag', 'revenue_stability') + \
              _build_flag_row("周期性", 'cyclicality_flag', 'cyclicality') + \
              _build_flag_row("护城河", 'moat_proxy_flag', 'moat')
              
    col_fin = _build_flag_row("资产负债表", 'balance_sheet_flag', 'balance_sheet') + \
              _build_flag_row("现金流覆盖", 'cashflow_coverage_flag', 'cashflow_coverage') + \
              _build_flag_row("杠杆风险", 'leverage_risk_flag', 'leverage_risk')
              
    col_gov = _build_flag_row("分红一致性", 'payout_consistency_flag', 'payout_consistency') + \
              _build_flag_row("稀释风险", 'dilution_risk_flag', 'dilution_risk') + \
              _build_flag_row("监管依赖", 'regulatory_dependence_flag', 'regulatory_dependence')

    # Assembly
    html = f"""
<div class="vera-card">
    <div class="vera-card-header">
        <span class="material-symbols-outlined" style="margin-right:10px;">verified</span>
        <span style="font-weight:700; color:#e2e8f0; font-size:0.9rem;">3. 质量与盈利 (Quality & Profitability)</span>
        <span class="vera-help-icon" style="font-size:0.85rem; opacity:0.7; margin-left:8px; cursor:help;" title="适用于所有策略的公司体质过滤器：评估财务健康度、盈利稳定性、治理质量。是买入、CSP、杠杆等高风险操作的前置检查。">ⓘ</span>
    </div>
    <div class="vera-card-body" style="display:block;">
        {html_status}
        
        <!-- Metrics Grid -->
        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:32px; border-bottom:1px solid var(--border-dark); padding-bottom:24px; margin-bottom:20px;">
            <div style="padding-right:16px;">{html_div}</div>
            <div style="padding-left:16px;">{html_earn}</div>
        </div>
        
        <!-- Details Expander (HTML) -->
        <details>
            <summary style="cursor:pointer; font-size:0.9rem; color:#94a3b8; padding:8px 0; user-select:none; outline:none;">
                🔍 展开查看质量标志位详情 (9 flags)
            </summary>
            <div style="margin-top:16px; display:grid; grid-template-columns:repeat(3, 1fr); gap:32px;">
                <div>
                    <div style="margin-bottom:8px; font-weight:600; font-size:0.85rem; color:#64748b;">商业质量 (Business)</div>
                    {col_biz}
                </div>
                <div style="padding-left:24px;">
                    <div style="margin-bottom:8px; font-weight:600; font-size:0.85rem; color:#64748b;">财务质量 (Financial)</div>
                    {col_fin}
                </div>
                <div style="padding-left:24px;">
                    <div style="margin-bottom:8px; font-weight:600; font-size:0.85rem; color:#64748b;">治理/政策 (Governance)</div>
                    {col_gov}
                </div>
            </div>
        </details>
    </div>
</div>
"""
    st.markdown(clean_html(html), unsafe_allow_html=True)

def render_ai_capex_card(data: DashboardData):
    """AI 基建 & CapEx 风险卡片 (AI CapEx Risk Overlay)"""
    ai = data.ai_capex_overlay
    if not ai or not ai.get("enabled", False):
        return

    scoring = ai.get("scoring", {})
    ui = ai.get("ui", {})
    
    badge = ui.get("headline_badge", {})
    label_zh = badge.get("label_zh", "AI 风险评估")
    tone = badge.get("tone", "info") # danger, warning, info
    
    colors = {"danger": "#ef4444", "warning": "#eab308", "info": "#3b82f6"}
    color = colors.get(tone, "#3b82f6")
    
    # 统一样式
    st.markdown(f"""
    <div id="ai-capex-anchor" style="height:0;"></div>
    <div class="vera-card">
        <div class="vera-card-header" style="background:{color}15; border-bottom:1px solid {color}30;">
            <span class="material-symbols-outlined" style="color:{color}; margin-right:10px;">bolt</span>
            <span class="vera-overlay-title" style="color:{color}; font-size:1.1rem;">{label_zh}</span>
        </div>
        <div style="padding:24px;">
            <div style="background:{color}08; border-left:4px solid {color}; padding:16px; border-radius:4px; margin-bottom:24px;">
                <div style="font-size:0.95rem; color:#f1f5f9; line-height:1.6;">{ui.get('summary_zh', '')}</div>
            </div>
    """, unsafe_allow_html=True)
    
    # 核心指标
    kn = ui.get("key_numbers", [])
    if kn:
        kn_cols = st.columns(len(kn))
        for idx, item in enumerate(kn):
            with kn_cols[idx]:
                val_str = str(item.get('value', '-'))
                if item.get('unit') == 'million':
                    try: val_str = f"${float(item['value']):,.0f}M"
                    except: pass
                elif isinstance(item.get('value'), float):
                    val_str = f"{item['value']:.1f}"
                
                st.markdown(f"""
                <div style="text-align:center;">
                    <div style="font-size:0.8rem; color:#94a3b8; margin-bottom:4px;">{item.get('label_zh')}</div>
                    <div style="font-size:1.5rem; font-weight:700; color:#f1f5f9;">{val_str}</div>
                </div>
                """, unsafe_allow_html=True)
    
    st.markdown("<div style='height:24px; border-bottom:1px dashed rgba(255,255,255,0.05); margin-bottom:24px;'></div>", unsafe_allow_html=True)
    
    # 维度评分
    d_cols = st.columns(4)
    dimensions = [
        ("开支强度", "capex_intensity_bucket"),
        ("折旧拖累", "depreciation_drag_bucket"),
        ("表外承诺", "off_balance_commitment_bucket"),
        ("租赁占比", "lease_capex_share_bucket")
    ]
    bucket_colors = {"HIGH": "#ef4444", "MEDIUM": "#eab308", "LOW": "#22c55e"}
    
    for idx, (label, key) in enumerate(dimensions):
        bucket = scoring.get(key, "N/A")
        b_color = bucket_colors.get(bucket, "#94a3b8")
        with d_cols[idx]:
            st.markdown(f"""
            <div style="background:rgba(255,255,255,0.03); padding:12px; border-radius:8px; text-align:center; border:1px solid rgba(255,255,255,0.05);">
                <div style="font-size:0.75rem; color:#94a3b8; margin-bottom:6px;">{label}</div>
                <div style="font-size:1rem; font-weight:700; color:{b_color};">{bucket}</div>
            </div>
            """, unsafe_allow_html=True)
            
    st.markdown("</div></div>", unsafe_allow_html=True)

def render_csp_eval_card(data: DashboardData, vera_result: dict = None, expert_mode: bool = False):
    """CSP (Cash Secured Put) 策略评估卡片"""
    from vera.engines.csp_permission_engine import CSPPermissionEngine
    
    # 1. Get Strategy Permission from PermissionEngine (vera_result)
    if vera_result and 'decision_cn' in vera_result:
        r_state = vera_result['decision_cn'].get('R_state', 'RED')  # Strategy layer permission
    else:
        # Fallback if VERA hasn't run yet
        r_state = 'RED'
    
    # 2. Run Contract Audit from CSPPermissionEngine
    csp_result = CSPPermissionEngine.evaluate_from_dashboard(data)
    contract_r_state = csp_result['R_state']
    metrics = csp_result['metrics']
    
    # 3. Strategy Layer Status Mapping
    strategy_status_map = {
        "GREEN": {"label": "允许正常仓位", "color": "#22c55e", "icon": "check_circle"},
        "YELLOW": {"label": "允许轻仓尝试", "color": "#f59e0b", "icon": "warning"},
        "RED": {"label": "禁止开仓", "color": "#ef4444", "icon": "block"}
    }
    strategy_info = strategy_status_map.get(r_state, strategy_status_map["RED"])
    
    # 4. Contract Audit Integration (CSP Part 3 - UI Integrated)
    from vera.engines.csp_contract_engine import get_csp_candidates, pick_best_csp_contract, calc_annual_yield
    
    best_contract = None
    all_audited = [] 
    
    # 1. Always fetch and audit (Regardless of r_state)
    # This allows viewing audit table even if strategy is RED
    current_price = metrics.get('current_price') or getattr(data, 'price', 0.0) or getattr(data, 'last_price', 0.0) or getattr(data, 'close', 0.0)
    candidates = get_csp_candidates("vera.db", data.symbol, current_price)
    best_contract, all_audited = pick_best_csp_contract(candidates)

    if r_state == "RED":
        contract_status = "SKIPPED"
        contract_label = "未审计 (策略禁止)"
        contract_color = "#64748b"
        contract_icon = "do_not_disturb"
        contract_message = "策略层面处于禁用状态 (RED)，系统禁止开仓。\n\n下方的期权审计表仅供投研参考。"
        
        # Init metrics from best_contract if available (for Expert Panel visibility)
        if best_contract:
            metrics = {
                'moneyness': -best_contract['discount_pct'],
                'annual_yield': calc_annual_yield(best_contract.get('mid', 0) or best_contract.get('bid', 0), best_contract['strike'], best_contract['dte']),
                'strike': best_contract['strike'],
                'days_to_expiry': best_contract['dte'],
                'current_price': current_price, 
                'option': {
                    'Delta': best_contract.get('delta', 0), 
                    'ExpiryDate': best_contract.get('expiry', '-'), 
                    'IV': 0
                }
            }
        else:
            metrics = {
                'moneyness': 0,
                'annual_yield': 0,
                'strike': 0,
                'days_to_expiry': 0,
                'option': {'Delta': 0, 'IV': 0, 'ExpiryDate': '-'}
            }
        
    elif not best_contract:
        contract_status = "NO_DATA"
        contract_label = "无数据"
        contract_color = "#64748b"
        contract_icon = "search_off"
        contract_message = "未找到符合条件的认沽期权数据（可能是期权链缺失或未导入）。请检查导入页面。"
        metrics = {
            'moneyness': 0, 'annual_yield': 0, 'strike': 0, 'days_to_expiry': 0,
            'option': {'Delta': 0, 'IV': 0, 'ExpiryDate': '-'}
        }
        
    else:
        # Extract audit result from the best contract found
        audit = best_contract["_audit"]
        contract_status = audit.status # APPROVED / REJECTED
        
        # Sync to metrics dict for downstream Rendering compatibility
        metrics['strike'] = best_contract['strike']
        metrics['days_to_expiry'] = best_contract['dte']
        metrics['moneyness'] = -best_contract['discount_pct'] # Negative implies OTM Put in some conventions
        metrics['option'] = {'Delta': best_contract['delta']}
        
        ay = calc_annual_yield(best_contract['mid'], best_contract['strike'], best_contract['dte'])
        metrics['annual_yield'] = ay

        if contract_status == "APPROVED":
            contract_label = "通过"
            contract_color = "#22c55e"
            contract_icon = "check_circle"
            # Format message with Markdown bolding
            contract_message = f"""策略许可：{strategy_info['label']}
            
当前推荐合约 (**Strike {best_contract['strike']}**) 已通过风险审计：
• 折价幅度：**{best_contract['discount_pct']:.1%}** (现价 {best_contract['spot']:.2f})
• 到期详情：{best_contract['expiry']} (剩余 {best_contract['dte']} 天)
• 收益评估：年化 **{ay:.1%}** (Delta: {best_contract['delta']}, Mid: {best_contract['mid']:.2f})

建议：{audit.suggestion}"""

        else: # REJECTED
            contract_status = "REJECTED"
            contract_label = "不通过"
            contract_color = "#ef4444"
            contract_icon = "cancel"
            
            reasons_text = "\n".join([f"• {r['message']}" for r in audit.reasons])
            
            contract_message = f"""策略许可：{strategy_info['label']}
            
当前最优合约 (**Strike {best_contract['strike']}**) 未通过审计 (评分 {audit.score:.0f})：
{reasons_text}

合约参数：DTE {best_contract['dte']}天, 年化 {ay:.1%}, Delta {best_contract['delta']}
建议：{audit.suggestion}"""
    
    # 5. Render with Three-Column Horizontal Layout
    st.markdown(f"""
<div class="vera-card">
<div class="vera-card-header">
<span class="material-symbols-outlined" style="margin-right:10px;">assignment_turned_in</span>
<span style="font-weight:700; color:#e2e8f0; font-size:0.9rem;">CSP 策略评估 (CSP Strategy Evaluation)</span>
<span class="vera-help-icon" style="font-size:0.85rem; opacity:0.7; margin-left:8px; cursor:help;" title="策略层：判断当前资产环境是否适合 CSP；合约层：审计具体 Put 合约参数。">ⓘ</span>
</div>
<div class="vera-card-body" style="display:block; padding:20px;">

<div style="display:grid; grid-template-columns: 1fr 1fr 1fr; gap:16px; align-items:start;">

<div style="background:rgba(255,255,255,0.02); border-left:3px solid {strategy_info['color']}; border-radius:6px; padding:14px;">
<div style="display:flex; align-items:center; gap:8px; margin-bottom:8px;">
<span class="material-symbols-outlined" style="font-size:18px; color:{strategy_info['color']};">{strategy_info['icon']}</span>
<span style="font-size:0.85rem; color:#94a3b8; font-weight:600;">策略许可 (Strategy Permission)</span>
</div>
<div style="font-size:1.05rem; font-weight:700; color:{strategy_info['color']};">{strategy_info['label']}</div>
</div>

<div style="background:rgba(255,255,255,0.02); border-left:3px solid {contract_color}; border-radius:6px; padding:14px;">
<div style="display:flex; align-items:center; gap:8px; margin-bottom:8px;">
<span class="material-symbols-outlined" style="font-size:18px; color:{contract_color};">{contract_icon}</span>
<span style="font-size:0.85rem; color:#94a3b8; font-weight:600;">合约审计 (Contract Audit)</span>
</div>
<div style="font-size:1.05rem; font-weight:700; color:{contract_color};">{contract_label}</div>
</div>

<div style="background:rgba(59, 130, 246, 0.06); border-left:3px solid #3b82f6; border-radius:6px; padding:14px;">
<div style="font-size:0.8rem; color:#cbd5e1; line-height:1.6; white-space:pre-line;">{contract_message}</div>
</div>

</div>
""", unsafe_allow_html=True)
    
    # 4. 展示关键指标 (Strict Action Gate Style with Embedded Rules)
    if metrics.get('strike', 0) > 0:
        c1, c2, c3 = st.columns(3, gap="medium")
        
    # 4. 展示关键指标 (Strict Action Gate Style with Custom CSS Tooltip)
    # Inject Specific CSS for CSP Tooltip (Blue Theme Style)
    st.markdown("""
    <style>
    .vera-tooltip-csp {
        position: relative;
        display: inline-block;
        cursor: help;
    }
    .vera-tooltip-csp .vera-tooltip-text {
        visibility: hidden;
        width: 280px;
        background: linear-gradient(135deg, #1a2942 0%, #1e3a5f 100%);
        color: #e2e8f0;
        text-align: left;
        border-radius: 10px;
        padding: 16px;
        position: absolute;
        z-index: 999999;
        bottom: 100%;
        left: 50%;
        margin-left: -140px;
        margin-bottom: 10px;
        opacity: 0;
        transition: opacity 0.3s ease;
        font-size: 0.85rem;
        font-weight: 400;
        line-height: 1.6;
        border: 1px solid rgba(96, 165, 250, 0.3);
        box-shadow: 0 10px 40px -10px rgba(0, 0, 0, 0.6), 0 0 0 1px rgba(255,255,255,0.05);
        pointer-events: none;
    }
    .vera-tooltip-csp:hover .vera-tooltip-text {
        visibility: visible;
        opacity: 1;
    }
    /* Arrow */
    .vera-tooltip-csp .vera-tooltip-text::after {
        content: "";
        position: absolute;
        top: 100%;
        left: 50%;
        margin-left: -6px;
        border-width: 6px;
        border-style: solid;
        border-color: #1e3a5f transparent transparent transparent;
    }
    .vera-tooltip-title {
        color: #60a5fa;
        font-weight: 700;
        font-size: 0.9rem;
        display: block;
        margin-bottom: 10px;
        padding-bottom: 8px;
        border-bottom: 1px solid rgba(96, 165, 250, 0.2);
    }
    .vera-tooltip-item {
        display: list-item;
        list-style-position: inside;
        margin-left: 8px;
        margin-bottom: 6px;
        color: #cbd5e1;
    }
    .vera-tooltip-item b {
        color: #93c5fd;
    }
    </style>
    """, unsafe_allow_html=True)

    if metrics.get('strike', 0) > 0:
        c1, c2, c3 = st.columns(3, gap="medium")
        
        # Helper to render styled box like Action Gate
        def render_metric_gate(col, label, main_val, sub_val, theme="BLUE", tooltip_html=""):
            if theme == "GREEN":
                c_hex = "#22c55e"
                bg = "rgba(34, 197, 94, 0.15)"
                glow = "0 4px 12px rgba(34, 197, 94, 0.1)"
                icon = "payments"
            elif theme == "RED":
                c_hex = "#ef4444"
                bg = "rgba(239, 68, 68, 0.12)"
                glow = "none"
                icon = "warning"
            elif theme == "YELLOW":
                c_hex = "#f59e0b"
                bg = "rgba(245, 158, 11, 0.12)"
                glow = "none"
                icon = "schedule"
            else: # BLUE/DEFAULT
                c_hex = "#3b82f6"
                bg = "rgba(59, 130, 246, 0.12)"
                glow = "0 4px 12px rgba(59, 130, 246, 0.1)"
                icon = "price_check"

            # Render HTML structure
            info_icon = ""
            if tooltip_html:
                # Use dedicated class .vera-tooltip-csp
                info_icon = f'<div class="vera-tooltip-csp" style="margin-left:6px; color:{c_hex}; opacity:0.8;">ⓘ<span class="vera-tooltip-text">{tooltip_html}</span></div>'

            col.markdown(f"""
<div style="background:{bg}; border-left:4px solid {c_hex}; border-radius:10px; padding:16px; height:100%; box-shadow:{glow}; display:flex; flex-direction:column; justify-content:space-between; overflow:visible;">
<div>
<div style="display:flex; align-items:center; margin-bottom:8px;">
<span class="material-symbols-outlined" style="font-size:18px; color:{c_hex}; opacity:0.9; margin-right:8px;">{icon}</span>
<span style="font-size:0.85rem; font-weight:700; color:#cbd5e1;">{label}</span>
{info_icon}
</div>
<div style="font-size:1.5rem; font-weight:700; color:#f1f5f9; letter-spacing:0.5px;">{main_val}</div>
</div>
<div style="margin-top:8px; border-top:1px solid rgba(255,255,255,0.05); padding-top:8px;">
<div style="font-size:0.75rem; color:#94a3b8;">{sub_val}</div>
</div>
</div>""", unsafe_allow_html=True)

        # 1. Strike (Blue)
        spot = metrics.get('spot', 0)
        moneyness = abs(metrics.get('moneyness', 0)) * 100
        strike = metrics.get('strike', 0)
        render_metric_gate(
            c1, 
            "行权价 (Strike)", 
            f"${strike:.2f}", 
            f"现价 ${spot:.2f} <span style='color:#3b82f6'>(折扣 {moneyness:.1f}%)</span>",
            theme="BLUE",
            tooltip_html="<span class='vera-tooltip-title'>🛡️ 行权价安全垫规则</span><span class='vera-tooltip-item'>• <b>Moneyness</b>: 必须 > 5%</span><span class='vera-tooltip-item'>• <b>解释</b>: CSP 需要足够的安全垫，行权价必须低于现价一定幅度，以防止轻易被穿仓。</span>"
        )
            
        # 2. Yield (Green)
        yld = metrics.get('annual_yield', 0) * 100
        premium = metrics['option'].get('Market_Price', 0)
        iv = metrics['option'].get('IV', 0)
        if iv < 1: iv *= 100
        render_metric_gate(
            c2, 
            "年化收益 (Yield)", 
            f"{yld:.1f}%", 
            f"权利金 ${premium:.2f} | IV {iv:.1f}%",
            theme="GREEN",
            tooltip_html="<span class='vera-tooltip-title'>💰 收益补偿规则</span><span class='vera-tooltip-item'>• <b>年化收益率</b>: 必须 > 8%</span><span class='vera-tooltip-item'>• <b>解释</b>: 卖出 Put 承担了接盘风险，必须有足够的权利金作为补偿。</span>"
        )
            
        # 3. Risk (Yellow/Red)
        days = metrics.get('days_to_expiry', 0)
        delta = metrics['option'].get('Delta', 0)
        expiry = metrics['option'].get('ExpiryDate', '-')
        risk_theme = "YELLOW" if days > 7 else "RED"
        render_metric_gate(
            c3, 
            "期限与风险", 
            f"{days} 天", 
            f"到期 {expiry} | Delta {delta:.3f}",
            theme=risk_theme,
            tooltip_html="<span class='vera-tooltip-title'>⚠️ 期限与 Delta 风控</span><span class='vera-tooltip-item'>• <b>Delta</b>: 绝对值 < 0.35</span><span class='vera-tooltip-item'>• <b>期限</b>: 15 - 90 天</span><span class='vera-tooltip-item'>• <b>解释</b>: 避免过大敞口，同时避免期限太短或太长。</span>"
        )
        
    else:
        # Only show import tip if we actually missed data, not if skipped by strategy
        if contract_status == "NO_DATA":
            st.info("💡 请在导入页面上传期权 CSV 数据，以获得针对具体合约的评估。")

    # Add Audit Table (Visible if data exists)
    if all_audited:
        from core.config_loader import load_csp_rules
        rules = load_csp_rules()
        prefs = rules.get("csp_contract_prefs", {})
        
        st.markdown("---")
        st.subheader("🔍 期权链审计详情 (Detailed Audit)")
        
        # 1. 审计标准展示 (Audit Criteria)
        with st.container():
            st.markdown("###### 📏 评价标准 (Evaluation Criteria)")
            ec1, ec2, ec3, ec4 = st.columns(4)
            p_dte = prefs.get('tenor_days', {})
            p_delta = prefs.get('delta', {})
            p_disc = prefs.get('moneyness', {})
            p_yld = prefs.get('return_metrics', {}) # Corrected key
            
            ec1.info(f"**期限 (DTE)**\n\n{p_dte.get('preferred_min', '-')}-{p_dte.get('preferred_max', '-')} 天")
            ec2.info(f"**Delta 范围**\n\n[{p_delta.get('min', '-')}, {p_delta.get('max', '-')}]")
            ec3.info(f"**最低折价 (Discount)**\n\n> {p_disc.get('min_discount_pct', 0)*100:.1f}%")
            ec4.info(f"**最低年化 (Yield)**\n\n> {p_yld.get('min_annualized_return', 0)*100:.1f}%") # Corrected key
        
        # 2. 评估列表 (Table)
        with st.expander(f"📑 所有库存期权评估明细 (All Candidates: {len(all_audited)})", expanded=True):
            t_data = []
            # Sort by Score descending for table view
            sorted_audited = sorted(all_audited, key=lambda x: x['_audit'].score, reverse=True)
            
            for c in sorted_audited:
                a = c["_audit"]
                mid = c.get('mid') or c.get('bid') or 0.0
                ay = calc_annual_yield(mid, c['strike'], c['dte'])
                
                # Reason formatting (Chinese)
                reason_short = ""
                if a.reasons:
                    reason_map = {
                        "DELTA_OUT_OF_RANGE": "Delta 超限 (过于激进或保守)",
                        "DISCOUNT_OUT_OF_RANGE": "折价不足 (行权价太近)",
                        "YIELD_TOO_LOW": "收益率过低",
                        "TENOR_TOO_SHORT": "期限过短",
                        "TENOR_TOO_LONG": "期限过长",
                        "NO_BID": "无买盘报价"
                    }
                    codes = [reason_map.get(r['code'], r['code']) for r in a.reasons]
                    reason_short = ", ".join(codes)
                
                status_icon = "✅" if a.status == "APPROVED" else "❌"
                
                # Format Delta
                d_val = c.get('delta')
                if isinstance(d_val, (int, float)):
                    d_str = f"{d_val:.3f}"
                else:
                    d_str = "-"
                
                # Format Yield (Handle NaN/Zero)
                if mid > 0 and ay is not None and ay == ay: # ay==ay checks for NaN
                    y_str = f"{ay:.1%}" if ay < 10 else ">1000%" # Cap crazy yields
                else:
                    y_str = "-"

                t_data.append({
                    "Strike": c['strike'],
                    "DTE": c['dte'],
                    "Yield": y_str,
                    "Discount": f"{c['discount_pct']:.1%}",
                    "Delta": d_str,
                    "Status": f"{status_icon} {a.status}",
                    "Score": int(a.score),
                    "Fail Reasons": reason_short
                })
            
            df_table = pd.DataFrame(t_data)
            st.dataframe(
                df_table, 
                use_container_width=True, 
                hide_index=True,
                column_config={
                    "Yield": st.column_config.TextColumn(help="年化收益率"),
                    "Score": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d", help="审计评分")
                }
            )
    
    # Expert Mode: Detailed Audit Panel
    if expert_mode:
        with st.expander("🔬 专家审计详情 (Expert Audit Details)", expanded=False):
            st.markdown("""
            <div style="background:rgba(59,130,246,0.05); border-left:3px solid #3b82f6; padding:12px; border-radius:6px; margin-bottom:16px;">
                <div style="font-size:0.85rem; color:#3b82f6; font-weight:600;">📋 审计说明</div>
                <div style="font-size:0.75rem; color:#94a3b8; margin-top:4px;">
                    本面板展示 CSP 合约审计的底层逻辑、规则来源和中间计算值，仅供专业投研人员复核使用。
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Section 1: Rule Configuration
            st.markdown("##### 1️⃣ 规则配置 (Rule Configuration)")
            rule_id = csp_result.get('rule_id', 'N/A')
            st.markdown(f"""
            - **规则 ID**: `{rule_id}`
            - **配置文件**: `config/csp_permission_rules.yaml`
            - **判定状态**: `{contract_r_state}` (合约层) / `{r_state}` (策略层)
            """)
            
            # Section 2: Intermediate Metrics
            st.markdown("##### 2️⃣ 中间计算指标 (Intermediate Metrics)")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric(
                    "Moneyness (行权价偏离)",
                    f"{metrics.get('moneyness', 0)*100:.2f}%",
                    help="行权价相对现价的偏离程度，负值表示虚值"
                )
                st.metric(
                    "年化收益率",
                    f"{metrics.get('annual_yield', 0)*100:.1f}%",
                    help="权利金年化收益率"
                )
            
            with col2:
                st.metric(
                    "Delta (绝对值)",
                    f"{abs(metrics['option'].get('Delta', 0)):.3f}",
                    help="Delta 绝对值，反映行权概率"
                )
                st.metric(
                    "到期天数",
                    f"{metrics.get('days_to_expiry', 0)} 天",
                    help="距离期权到期的剩余天数"
                )
            
            with col3:
                st.metric(
                    "隐含波动率 (IV)",
                    f"{metrics['option'].get('IV', 0)*100:.1f}%",
                    help="期权隐含波动率"
                )
                st.metric(
                    "估值分位 (10Y)",
                    f"{metrics.get('valuation_pct_10y', 0):.1f}%",
                    help="当前 PE 在 10 年历史中的分位数"
                )
            
            # Section 3: Threshold Comparison
            st.markdown("##### 3️⃣ 阈值对比 (Threshold Comparison)")
            
            thresholds = [
                {"name": "估值分位上限", "value": metrics.get('valuation_pct_10y', 0), "threshold": 70, "unit": "%", "pass": metrics.get('valuation_pct_10y', 0) <= 70, "icon": "📊"},
                {"name": "Delta 上限", "value": abs(metrics['option'].get('Delta', 0)), "threshold": 0.35, "unit": "", "pass": abs(metrics['option'].get('Delta', 0)) < 0.35, "icon": "📈"},
                {"name": "收益率下限", "value": metrics.get('annual_yield', 0)*100, "threshold": 8, "unit": "%", "pass": metrics.get('annual_yield', 0)*100 > 8, "icon": "💰"},
                {"name": "期限下限", "value": metrics.get('days_to_expiry', 0), "threshold": 15, "unit": "天", "pass": metrics.get('days_to_expiry', 0) >= 15, "icon": "⏱️"},
                {"name": "期限上限", "value": metrics.get('days_to_expiry', 0), "threshold": 90, "unit": "天", "pass": metrics.get('days_to_expiry', 0) <= 90, "icon": "⏱️"},
            ]
            
            # Render as 3-column grid
            threshold_html = '<div style="display:grid; grid-template-columns: 1fr 1fr 1fr; gap:12px; margin-top:12px;">'
            
            for t in thresholds:
                status_icon = "✅" if t['pass'] else "❌"
                status_color = "#22c55e" if t['pass'] else "#ef4444"
                bg_color = "rgba(34, 197, 94, 0.08)" if t['pass'] else "rgba(239, 68, 68, 0.08)"
                threshold_html += f'<div style="background:{bg_color}; border-left:3px solid {status_color}; border-radius:6px; padding:12px;"><div style="display:flex; align-items:center; gap:6px; margin-bottom:6px;"><span style="font-size:1rem;">{t["icon"]}</span><span style="font-size:0.75rem; color:#94a3b8; font-weight:600;">{t["name"]}</span><span style="font-size:0.9rem; margin-left:auto;">{status_icon}</span></div><div style="font-size:1.1rem; font-weight:700; color:{status_color}; margin-bottom:2px;">{t["value"]:.2f}{t["unit"]}</div><div style="font-size:0.7rem; color:#64748b;">阈值: {t["threshold"]}{t["unit"]}</div></div>'
            
            threshold_html += '</div>'
            st.markdown(threshold_html, unsafe_allow_html=True)
            
            # Section 4: Full Result JSON
            st.markdown("##### 4️⃣ 完整审计报文 (Full Audit Payload)")
            if st.checkbox("显示完整 JSON", key="csp_expert_json"):
                st.json(csp_result)
        
    st.markdown("</div></div>", unsafe_allow_html=True)


def render_behavior_card(data: DashboardData, profile: Optional[RiskProfile] = None):
    """5. 行为与认知 (Behavior & Cognition) - Unified Card"""
    
    # Logic extraction
    
    # 1. Behavior Suggestion (Col 1)
    sugg = data.behavior_suggestion or "暂无建议"
    
    # 2. Cognitive Warning (Col 2)
    cog_text = data.cognitive_warning or "正常风险范围"
    cog_color = "#9ca3af" # Gray
    if profile and data.risk_card:
        risk_alert = detect_risk_combination(data, profile)
        if risk_alert:
            level, title, msg = risk_alert
            cog_text = f"**{title}**<br>{msg}"
            if level == "极高": cog_color = "#ef4444"
            elif level == "高": cog_color = "#f59e0b"
            else: cog_color = "#3b82f6"
    
    html_cog = f'<span style="color:{cog_color}">{cog_text}</span>'
    
    # 3. Next Action / Flags (Col 3)
    # Combining the flags or just the simple action logic
    action_html = ""
    if "禁止" in sugg: action_html = '<span style="color:#ef4444">🚫 观望为主</span>'
    elif "避免" in sugg: action_html = '<span style="color:#f59e0b">⏸️ 等待时机</span>'
    elif "建议" in sugg or "分批" in sugg: action_html = '<span style="color:#22c55e">✅ 分批建仓</span>'
    else: action_html = '<span style="color:#3b82f6">👀 持续监控</span>'
    
    # Grid HTML
    
    # Column 1
    html_c1 = _get_metric_html_string("行为建议 (Suggestion)", sugg, help_text="基于当前技术面与基本面状态的综合操作建议。")
    
    # Column 2
    html_c2 = _get_metric_html_string("认知预警 (Cognitive)", html_cog, help_text="检测是否存在由于非理性认知导致的潜在风险。")
    
    # Column 3
    html_c3 = _get_metric_html_string("下一步行动 (Next Step)", action_html, help_text="当前状态下的推荐行动方案。")

    html = f"""
<div class="vera-card">
    <div class="vera-card-header">
        <span style="font-weight:700; color:#e2e8f0; font-size:0.9rem;">5. 行为与认知 (Behavior & Cognition)</span>
    </div>
    <div class="vera-card-body" style="grid-template-columns: repeat(3, 1fr); gap: 32px;">
        <div style="padding-right:24px;">{html_c1}</div>
        <div style="padding:0 8px;">{html_c2}</div>
        <div style="padding-left:24px;">{html_c3}</div>
    </div>
</div>
"""
    st.markdown(clean_html(html), unsafe_allow_html=True)



def render_risk_overlay(data: DashboardData, vera_result: Optional[dict] = None, expert_mode: bool = False):
    """1. 风险来源对照 (Risk Overlay) - Simplified/Card Style"""
    # Note: Header is now part of the unified card

    ov = data.overlay or {}
    # Support new standard keys (individual/sector/market) with fallback to legacy
    asset_risk = ov.get("individual") or ov.get("asset_risk") or {}
    sector_risk = ov.get("sector") or ov.get("sector_risk") or {}
    market_risk = ov.get("market") or ov.get("market_risk") or {}

    # Extract Volatilities for Deep Dive Extension
    v_ind = asset_risk.get('volatility_1y') or data.volatility
    v_sec = sector_risk.get('volatility_1y')
    v_mkt = market_risk.get('volatility_1y')

    # Helper: Formatter for D-State Structure
    def _fmt_state(state_node):
        if not state_node or not isinstance(state_node, dict): return "-"
        code = state_node.get("code", "")
        label = state_node.get("label_zh") or state_node.get("label", "")
        if not code: return "-"
        return f"{code} · {label}" if label else code

    # Helper: Progress Logic based on State or Position
    def _get_progress_props(state_code, path_risk=None):
        # Returns (width_pct, color_hex)
        code_str = str(state_code).split()[0]
        suffix = code_str[1:] if len(code_str) > 1 else ""
        
        # Color primarily driven by Path Risk for visual alignment
        if path_risk == "HIGH":
            color = "#ef4444" # Red
        elif path_risk == "MID":
            color = "#f59e0b" # Amber/Orange
        elif path_risk == "LOW":
            # Select color based on state within LOW risk
            if suffix == "0": color = "#f8fafc" # White
            elif suffix == "1": color = "#3b82f6" # Blue
            else: color = "#10b981" # Emerald
        else:
            color = "#64748b" # Gray fallback
            
        # Width represents cycle progress
        width_map = {"0": 100, "1": 90, "2": 70, "3": 40, "4": 25, "5": 60, "6": 95}
        width = width_map.get(suffix, 50)
            
        return width, color

    def _render_layer_panel(label, risk_node, sub_label="", top_id=None, vol_1y=None):
        state_code = risk_node.get("state")
        label_zh = risk_node.get("label_zh")
        path_risk_raw = risk_node.get("path_risk")
        dd = risk_node.get("drawdown") or {}
        
        curr_dd = dd.get("current_dd_pct", 0.0)
        max_dd = dd.get("max_dd_10y_pct", -1.0)
        
        abs_curr = abs(curr_dd)
        abs_max = abs(max_dd)
        rel_strength = (abs_curr / abs_max) * 100 if abs_max > 0.001 else 0.0

        # Dynamic Color for Relative MDD Bar
        if rel_strength < 25:
             rel_bar_color = "#22c55e" # Green
        elif rel_strength < 50:
             rel_bar_color = "#84cc16" # Lime
        elif rel_strength < 75:
             rel_bar_color = "#eab308" # Yellow
        else:
             rel_bar_color = "#ef4444" # Red

        # Tooltip Text Generation
        state_type = "I_STATE" if "大盘" in label else "D_STATE"
        state_tooltip = get_legend_text(state_type, format="html")
        r_state_tooltip = get_legend_text("R_STATE", format="html")
        vol_tooltip = get_legend_text("VOLATILITY_1Y", format="html")
        rel_mdd_tooltip = get_legend_text("REL_MDD", format="html")
        path_tooltip = get_legend_text("PATH_RISK", format="html")

        # Recent Cycle Data
        recent = risk_node.get("recent_cycle", {})
        recent_html = ""
        r_state_text = "-"
        r_c = "#94a3b8"
        
        if recent:
            off_high = recent.get("max_dd_1y", 0.0) * 100
            days = recent.get("dd_days", 0)
            sigma = recent.get("dd_sigma", 0.0)
            r_state = recent.get("state", "").split("_")[0] 
            r_label = recent.get("label", "")
            r_state_text = f"{r_state} · {r_label}"
            sigma_str = f"{sigma:.1f}σ" if sigma > 0 else "-"
            
            r_color_map = {
                "R0": "#94a3b8", "R1": "#cbd5e1", 
                "R2": "#f59e0b", "R3": "#ea580c", "R4": "#ef4444"
            }
            r_c = r_color_map.get(r_state, "#94a3b8")
            
            # Details Card Content
            dd_val_str = f"{off_high:.1f}%"
            peak_date_str = recent.get("peak_date", "-")
            
            # R-State Header & Metrics (Consistent Layout)
            recent_html = f"""
            <!-- RECENT INTERVAL DIVIDER -->
            <div style="margin: 20px 0 15px 0; display:flex; align-items:center; justify-content:center; gap:12px; opacity:0.4;">
                <div style="flex:1; height:1px; background:rgba(255,255,255,0.1);"></div>
                <span style="font-size:0.55rem; letter-spacing:1.5px; font-weight:800; color:#94a3b8; text-transform:uppercase;">RECENT INTERVAL</span>
                <div style="flex:1; height:1px; background:rgba(255,255,255,0.1);"></div>
            </div>

            <!-- R-STATE ROW -->
            <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:5px;">
                <div class="vera-tooltip" style="cursor:help;">
                    <h2 style="font-size:1.6rem; font-weight:800; color:#f1f5f9; margin:0; letter-spacing:-0.5px;">{r_state_text}</h2>
                    <span class="vera-tooltip-text">{r_state_tooltip}</span>
                </div>
                <div style="background:rgba(255,255,255,0.03); color:#64748b; padding:3px 8px; border-radius:4px; font-size:0.55rem; font-weight:700; border:1px solid rgba(255,255,255,0.05);">近期周期 (1Y)</div>
            </div>

            <!-- R-STATE METRICS -->
            <div style="margin: 10px 0 0 0; display:flex; gap:24px;">
                <!-- Left: Maximum Drawdown -->
                <div style="flex:1;">
                     <div style="font-size:0.65rem; color:#64748b; font-weight:600; margin-bottom:4px;">近期最大回撤 (MAX DRAWDOWN)</div>
                     <div style="font-size:1.4rem; font-weight:800; color:#f1f5f9; margin-bottom:2px;">{dd_val_str}</div>
                     <div style="font-size:0.65rem; color:#64748b;"><span style="color:#f1f5f9;">{days}</span> 天 (自 {peak_date_str})</div>
                </div>
                
                <!-- Right: Recovery -->
                <div style="flex:1; border-left:1px solid rgba(255,255,255,0.1); padding-left:24px;">
                    <div style="font-size:0.65rem; color:#64748b; font-weight:600; margin-bottom:4px; white-space:nowrap;">修复进度 (RECOVERY)</div>
                    <div style="font-size:1.4rem; font-weight:800; color:#f1f5f9; margin-bottom:2px;">{recent.get('recovery_pct', 0.0)*100:.1f}%</div>
                    {f'<div style="font-size:0.65rem; color:#64748b;">{"已耗时" if recent.get("recovery_pct", 0.0) < 1.0 else "共耗时"} <span style="color:#ef4444; font-weight:700;">{recent.get("recovery_days", 0)}</span> 天</div>' if recent.get('recovery_days', 0) > 0 else ''}
                </div>
            </div>

            <!-- R-STATE NARRATIVE (ADVANCED ANALYTICS) -->
            <div style="margin-top:12px; padding-top:10px; border-top:1px dashed rgba(255,255,255,0.05); font-size:0.65rem; color:#94a3b8; line-height:1.5;">
                <span style="color:#64748b; font-weight:700;">分析概览：</span>
                {recent.get('risk_narrative', '')}
            </div>
            """

        p_c = "#22c55e" if path_risk_raw == "LOW" else "#eab308" if path_risk_raw == "MID" else "#ef4444" if path_risk_raw == "HIGH" else "#64748b"
        p_bg = "rgba(34, 197, 94, 0.1)" if path_risk_raw == "LOW" else "rgba(234, 179, 8, 0.1)" if path_risk_raw == "MID" else "rgba(239, 68, 68, 0.1)" if path_risk_raw == "HIGH" else "rgba(100, 116, 139, 0.1)"
        path_badge = f"""
        <div class="vera-tooltip" style="cursor:help;">
            <div style="background:{p_bg}; color:{p_c}; padding:3px 10px; border-radius:20px; font-size:0.6rem; border:1px solid {p_c}33; display:flex; align-items:center; gap:5px; font-weight:700;">
                <span style="width:5px; height:5px; background:{p_c}; border-radius:50%;"></span>
                路径风险：{translate(path_risk_raw, 'zh_only')}
            </div>
            <span class="vera-tooltip-text">{path_tooltip}</span>
        </div>
        """

        w, color_code = _get_progress_props(state_code, path_risk=path_risk_raw)
        st_fmt = f"{state_code} · {label_zh}" if state_code and label_zh else (state_code or "-")
        id_display = top_id.split(":")[-1] if top_id else "-"
        layer_label = "ASSET RISK ANALYSIS" if "个股" in label else "SECTOR RISK ANALYSIS" if "板块" in label else "MARKET RISK ANALYSIS"
        
        return f"""
        <div style="background:rgba(15, 23, 42, 0.2); border:1px solid rgba(255,255,255,0.06); border-radius:16px; padding:24px; height:100%; display:flex; flex-direction:column; font-family: 'Inter', sans-serif;">
            <!-- TOP HEADER -->
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px; padding-bottom:12px; border-bottom:1px solid rgba(255,255,255,0.03);">
                <div style="display:flex; align-items:center; gap:10px;">
                    <span style="font-size:0.6rem; font-weight:800; color:#475569; letter-spacing:0.5px;">{layer_label}</span>
                    <span style="background:rgba(255,255,255,0.05); color:#94a3b8; padding:2px 8px; border-radius:4px; font-size:0.6rem; font-family:monospace; border:1px solid rgba(255,255,255,0.05);">{id_display}</span>
                </div>
                {path_badge}
            </div>

            <!-- D-STATE ROW -->
            <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:5px;">
                <div class="vera-tooltip" style="cursor:help;">
                    <h2 style="font-size:1.6rem; font-weight:800; color:#f1f5f9; margin:0; letter-spacing:-0.5px;">{st_fmt}</h2>
                    <span class="vera-tooltip-text">{state_tooltip}</span>
                </div>
                <div style="background:rgba(255,255,255,0.03); color:#64748b; padding:3px 8px; border-radius:4px; font-size:0.55rem; font-weight:700; border:1px solid rgba(255,255,255,0.05);">长期周期 (10Y)</div>
            </div>

            <!-- MDD INFO & RECOVERY -->
            <div style="margin: 10px 0 0 0; display:flex; gap:24px;">
                <!-- Left: MDD -->
                <div style="flex:1;">
                    <div style="font-size:0.65rem; color:#64748b; font-weight:600; margin-bottom:4px;">历史最大回撤 (10Y MAX DD)</div>
                    <div style="font-size:1.4rem; font-weight:800; color:#f1f5f9; margin-bottom:2px;">{max_dd*100:.1f}%</div>
                    <div style="font-size:0.65rem; color:#64748b;">({dd.get('mdd_peak_date', '-')} ~ {dd.get('mdd_valley_date', '-')} · <span style="color:#f1f5f9;">{dd.get('mdd_duration_days', 0)}</span> 天)</div>
                </div>

                <!-- Right: Recovery -->
                <div style="flex:1; border-left:1px solid rgba(255,255,255,0.1); padding-left:24px;">
                    <div style="font-size:0.65rem; color:#64748b; font-weight:600; margin-bottom:4px; white-space:nowrap;">修复进度 (RECOVERY)</div>
                    <div style="font-size:1.4rem; font-weight:800; color:#f1f5f9; margin-bottom:2px;">{dd.get('recovery_pct', 0.0)*100:.0f}%</div>
                    <div style="font-size:0.65rem; color:#64748b;">从历史大坑修复 ({"共耗时" if dd.get('recovery_pct', 0.0) >= 1.0 else "已耗时"} <span style="color:#f1f5f9;">{dd.get('recovery_days', 0)}</span> 天)</div>
                </div>
            </div>

            {recent_html}

            <!-- ANNUAL VOLATILITY (MERGED) -->
            <div style="margin: 15px 0 30px 0; padding-top:12px; border-top:1px solid rgba(255,255,255,0.03);">
                <div class="vera-tooltip" style="cursor:help; display:inline-block; margin-bottom:4px;">
                    <span style="font-size:0.65rem; color:#64748b; font-weight:600;">年化波动率 (VOLATILITY, 1Y)</span>
                    <span class="vera-tooltip-text">{vol_tooltip}</span>
                </div>
                <div style="font-size:1.4rem; font-weight:800; color:#f1f5f9;">{f"{vol_1y*100:.1f}%" if vol_1y is not None else "-"}</div>
            </div>

            <!-- PROGRESS SECTION -->
            <div style="margin-top:auto;">
                <div style="margin-bottom:12px;">
                    <div class="vera-tooltip" style="cursor:help; display:inline-block; margin-bottom:4px;">
                        <span style="font-size:0.6rem; font-weight:800; color:#475569; letter-spacing:0.5px; text-transform:uppercase;">相对历史最大回撤 (RELATIVE HISTORY MAX DRAWDOWN)</span>
                        <span class="vera-tooltip-text">{rel_mdd_tooltip}</span>
                    </div>
                    <div style="font-size:1.4rem; font-weight:800; color:#f1f5f9;">{rel_strength:.0f}%</div>
                </div>
                
                <div style="height:8px; background:rgba(255,255,255,0.04); border-radius:10px; position:relative; overflow:hidden; margin-bottom:8px;">
                    <div style="position:absolute; top:0; left:0; height:100%; width:{rel_strength}%; background:{rel_bar_color}; border-radius:10px; box-shadow: 0 0 10px {rel_bar_color}66;"></div>
                </div>
                
                <div style="display:flex; justify-content:space-between; font-size:0.55rem; color:#475569; font-weight:600; text-transform:uppercase;">
                    <span>MIN (0%)</span>
                    <span style="margin-left:-20px;">25%</span>
                    <span>50%</span>
                    <span style="margin-right:-20px;">75%</span>
                    <span>MAX (100%)</span>
                </div>
            </div>
            
            <!-- FOOTER ACTIONS -->
            <div style="margin-top:25px; padding-top:15px; border-top:1px solid rgba(255,255,255,0.03); display:flex; justify-content:flex-end; gap:15px; align-items:center; opacity:0.7;">
                <div style="display:flex; align-items:center; gap:5px; font-size:0.6rem; font-weight:700; color:#64748b; cursor:pointer;">
                    <span>↺</span> HISTORY
                </div>
                <div style="width:1px; height:10px; background:rgba(255,255,255,0.1); margin:0 5px;"></div>
                <div style="display:flex; align-items:center; gap:5px; font-size:0.6rem; font-weight:700; color:#64748b; cursor:pointer;">
                    <span>⤓</span> REPORT
                </div>
            </div>
        </div>
        """

    c1_html = _render_layer_panel("个股层级 (Asset)", asset_risk, sub_label="个股 (Stock)", top_id=asset_risk.get("id"), vol_1y=v_ind)
    c2_html = _render_layer_panel("板块层级 (Sector)", sector_risk, sub_label=sector_risk.get("name", "Sector"), top_id=sector_risk.get("id"), vol_1y=v_sec)
    c3_html = _render_layer_panel("大盘层级 (Market)", market_risk, sub_label=market_risk.get("name", "Market"), top_id=market_risk.get("id"), vol_1y=v_mkt)

    # Attribution Summary & Flags Grouping
    summary_text = ov.get("summary", "正在分析风险归因信息...")
    all_flags = ov.get("flags") or []
    
    # Categorize Flags
    ind_f, sec_f, mkt_f = [], [], []
    for f in all_flags:
        code = f.get("code", "")
        if "INDIVIDUAL" in code or "STOCK_SECTOR" in code or "STOCK_MKT" in code:
            ind_f.append(f)
        elif "SECTOR" in code:
            sec_f.append(f)
        elif "SYSTEMIC" in code or "REGIME" in code:
            mkt_f.append(f)
        else:
            # Fallback for mixed or unknown
            ind_f.append(f)

    def _render_flag_group(flags_list, empty_label="各项指标表现均衡"):
        if not flags_list: 
            return f"""
            <div style="height:100%; display:flex; align-items:center; justify-content:center; border:1px dashed rgba(255,255,255,0.05); border-radius:6px; background:rgba(255,255,255,0.01); color:#475569; font-size:0.75rem; padding:20px;">
                {empty_label}
            </div>
            """
            
        html = '<div style="display:flex; flex-direction:column; gap:8px;">'
        for f in flags_list:
            lvl_color = "#ef4444" if f.get("level") == "HIGH" else "#eab308" if f.get("level") == "MED" else "#64748b"
            bg_color = "rgba(239,68,68,0.05)" if f.get("level") == "HIGH" else "rgba(234,179,8,0.05)" if f.get("level") == "MED" else "rgba(255,255,255,0.02)"
            border_color = "rgba(239,68,68,0.2)" if f.get("level") == "HIGH" else "rgba(234,179,8,0.2)" if f.get("level") == "MED" else "rgba(255,255,255,0.05)"
            
            # Extract numerical values from detail if possible (e.g. -15.47%)
            detail = f.get('detail', '')
            import re
            m = re.search(r"(-?\d+\.?\d*%)", detail)
            val = m.group(1) if m else "?"
            
            # Clean detail: remove value and trailing punctuation
            clean_detail = detail.replace(val, "") if m else detail
            clean_detail = clean_detail.strip(" =,.:") # Clean trailing symbols
            
            # Use 'Card' layout similar to top panels
            # Label (Title) -> Big Value -> Desc
            
            val_html = f'<div style="font-size:1.1rem; font-weight:700; color:{lvl_color}; margin:2px 0;">{val}</div>' if val != "?" else ""
            
            html += f"""
            <div style="background:{bg_color}; border:1px solid {border_color}; border-radius:6px; padding:12px; position:relative; overflow:hidden;">
                <!-- Left Strip -->
                <div style="position:absolute; left:0; top:0; bottom:0; width:3px; background:{lvl_color};"></div>
                
                <div style="padding-left:8px;">
                     <!-- Title (Label style) -->
                     <div style="font-size:0.65rem; font-weight:700; color:#64748b; text-transform:uppercase; letter-spacing:0.05em; margin-bottom:2px;">
                        {f.get('title')}
                     </div>
                     
                     <!-- Big Value -->
                     {val_html}
                     
                     <!-- Description -->
                     <div style="font-size:0.7rem; color:#94a3b8; line-height:1.3; margin-top:4px;">
                        {clean_detail}
                     </div>
                </div>
            </div>
            """
        html += '</div>'
        return html

    ind_flags_html = _render_flag_group(ind_f)
    sec_flags_html = _render_flag_group(sec_f)
    mkt_flags_html = _render_flag_group(mkt_f)

    full_html = f"""
<div class="vera-card">
    <div class="vera-card-header" style="border-bottom: 1px solid rgba(255,255,255,0.05); margin-bottom: 20px; padding-bottom: 12px;">
        <span style="font-weight:700; color:#e2e8f0; font-size:0.9rem;">1. 风险来源对照 (Risk Overlay)</span>
        <span style="font-size:0.75rem; color:#64748b; margin-left:8px;">(Alignment Rebuilt)</span>
    </div>
    
    <!-- Row 1: Panels -->
    <div class="vera-card-body" style="grid-template-columns: repeat(3, 1fr); gap: 32px; margin-bottom: 24px;">
        <div style="padding-right:12px; border-right: 1px solid rgba(255,255,255,0.03);">{c1_html}</div>
        <div style="padding:0 8px; border-right: 1px solid rgba(255,255,255,0.03);">{c2_html}</div>
        <div style="padding-left:12px;">{c3_html}</div>
    </div>

    <!-- Attribution Summary Section -->
    <div style="background: rgba(0,0,0,0.15); padding: 16px; border-radius: 8px; border-left: 3px solid #3b82f6;">
        <div style="font-size: 0.8rem; font-weight: 700; color: #3b82f6; text-transform: uppercase; margin-bottom: 12px; letter-spacing: 0.05em; border-bottom: 1px solid rgba(59,130,246,0.1); padding-bottom:8px;">
            归因分析结论 (Attribution Summary)
        </div>
        
        <!-- Summary Text -->
        <div style="font-size: 0.9rem; color: #f1f5f9; line-height: 1.5; margin-bottom: 20px; font-weight:500;">
            {summary_text}
        </div>

        <!-- Row 2: Flags in 3 Columns (One Row Three Columns Layout) -->
        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 32px;">
            <div style="border-right: 1px solid rgba(255,255,255,0.03); padding-right:12px;">
                <div style="font-size:0.65rem; color:#64748b; font-weight:700; margin-bottom:8px; text-transform:uppercase;">个股项 (Individual)</div>
                {ind_flags_html}
            </div>
            <div style="border-right: 1px solid rgba(255,255,255,0.03); padding-right:12px;">
                <div style="font-size:0.65rem; color:#64748b; font-weight:700; margin-bottom:8px; text-transform:uppercase;">板块项 (Sector)</div>
                {sec_flags_html}
            </div>
            <div>
                <div style="font-size:0.65rem; color:#64748b; font-weight:700; margin-bottom:8px; text-transform:uppercase;">市场项 (Market)</div>
                {mkt_flags_html}
            </div>
        </div>
    </div>
</div>
"""
    st.markdown(clean_html(full_html), unsafe_allow_html=True)



# Shared Helper for HTML Metrics (Internal to this section)
def _get_metric_html_string(label, value, delta=None, delta_color="normal", help_text="", details="", box_class="vera-metric-card"):
    cursor_style = 'cursor: help;' if help_text else ''
    help_icon_html = ""
    help_overlay_html = ""
    if help_text:
        if "vera-tooltip-trigger" not in box_class:
            box_class += " vera-tooltip-trigger"
        help_overlay_html = f'<div class="metric-help-overlay">{help_text}</div>'
        help_icon_html = f'<span class="vera-help-icon">ⓘ</span>'
    
    details_html = ""
    if details:
        details_html = f'<div class="inline-metric-details">{details}</div>'
            
    delta_html = ""
    if delta:
        d_cls = "delta-up" if delta_color == "normal" else "delta-down"
        delta_html = f'<span class="inline-metric-delta {d_cls}">{delta}</span>'

    return f"""
    <div class="{box_class}" style="{cursor_style}; height:100%; min-height:100px; display:flex; flex-direction:column; justify-content:center;">
        <div class="vera-metric-label vera-tooltip-trigger">
            {label} {help_icon_html}
            {help_overlay_html}
        </div>
        <div class="vera-metric-value">{value}</div>
        {delta_html}
        {details_html}
    </div>
    """


def render_valuation_chart_content(data: DashboardData, chart_start_date=None, chart_end_date=None):
    """Render the Valuation Chart inside an expander or container"""
    try:
        from analysis.valuation import get_valuation_history
        hist_df = get_valuation_history(data.symbol, years=10, start_date=chart_start_date, end_date=chart_end_date)
        
        if data.report_date:
            try:
                cutoff_date = pd.to_datetime(data.report_date)
                if 'trade_date' in hist_df.columns:
                    hist_df['trade_date'] = pd.to_datetime(hist_df['trade_date'])
                    hist_df = hist_df[hist_df['trade_date'] <= cutoff_date]
            except: pass

        if not hist_df.empty and 'price' in hist_df.columns and 'pe' in hist_df.columns:
            import plotly.graph_objects as go
            from plotly.subplots import make_subplots
            plot_df = hist_df.copy()
            # 动态或更高的裁剪上限，支持 TSLA 等高倍数个股 (Fix: 150 -> 500)
            plot_df['pe_display'] = plot_df['pe'].clip(lower=-20, upper=500)
            
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            fig.add_trace(
                go.Scatter(x=plot_df['trade_date'], y=plot_df['price'], 
                           name="股价", line=dict(color='#475569', width=1), opacity=0.5),
                secondary_y=True,
            )
            
            if 'driver_phase' in plot_df.columns:
                phase_colors = {"Healthy": "#10b981", "Overheated": "#ef4444", "Neutral": "#94a3b8"}
                for phase, color in phase_colors.items():
                    p_data = plot_df[plot_df['driver_phase'] == phase]
                    if not p_data.empty:
                        fig.add_trace(
                            go.Scatter(x=p_data['trade_date'], y=p_data['price'], mode='markers', 
                                       name=f"驱动: {phase}", marker=dict(color=color, size=5)),
                            secondary_y=True,
                        )

            fig.add_trace(
                go.Scatter(x=plot_df['trade_date'], y=plot_df['pe_display'], 
                           name="市盈率 (PE)", line=dict(color='#f59e0b', width=2)),
                secondary_y=False,
            )

            pe_median = plot_df['pe'].median()
            fig.add_hline(y=pe_median, line_dash="dash", line_color="#f59e0b", opacity=0.4)

            fig.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=0, r=0, t=40, b=0),
                height=450,
                hovermode="x unified",
                xaxis=dict(title="日期"),
                yaxis=dict(title="PE Ratio"),
                yaxis2=dict(title="Price", overlaying='y', side='right', showgrid=False)
            )

            st.plotly_chart(fig, use_container_width=True, config={'displaylogo': False})

        else:
             st.caption("暂无足够数据生成走势图")
    except Exception as e:
        st.error(f"图表加载失败: {str(e)}")

def render_valuation_card(data: DashboardData, chart_start_date=None, chart_end_date=None):
    """3. 价值评估 (Valuation) - Unified with Chart"""
    v = data.value
    if not v:
        st.info("ℹ️ 估值数据仍在计算中...")
        return

    # 1. Status & Quality (Row 1)
    status_key = v.get('valuation_status_key', "UNKNOWN")
    score = v.get('pe_percentile', 50)
    
    # Precise Color & Label Logic based on vera_rules.yaml (v2.6)
    if status_key == "DEEP_UNDERVALUE":
        s_color, s_text = "#1D976C", "低估/深度"
    elif status_key == "FAIR_LOW":
        s_color, s_text = "#33B37B", "合理偏低"
    elif status_key == "FAIR":
        s_color, s_text = "#999999", "合理"
    elif status_key == "OVERVALUE":
        s_color, s_text = "#E67E22", "高估"
    elif status_key == "EXTREME_OVERVALUE":
        s_color, s_text = "#C0392B", "严重高估"
    else:
        s_color, s_text = "#F57C00", "合理"

    html_status = _get_metric_html_string("估值状态 (Valuation Status)", 
                                          f'<span style="color:{s_color}; font-weight:700;">{s_text}</span>',
                                          help_text=f"估值水位：反映当前估值相对于过去 10 年历史区间的热度。分位值越高表示当前估值越贵。判定标准：<br>• 0-15%：低估/深度区域<br>• 15-35%：合理偏低区域<br>• 35-75%：合理稳定区域<br>• 75-90%：明显高估区域<br>• 90-100%：严重高估区域。")

    # Quality Check
    q_check = v.get('quality_check', "PASS")
    if q_check == "PASS":
        q_html = '<div style="font-size:1.1rem;">无异常 <span style="font-size:0.8rem; opacity:0.7;">✓ 通过</span></div>'
    else:
        q_html = f'<div style="font-size:1.1rem; color:#ef4444;">存在异常 <span style="font-size:0.8rem;">⚠️ {q_check}</span></div>'
    
    html_quality = _get_metric_html_string("质量检测 (Quality Detection)", q_html, help_text=get_legend_text("QUALITY_FIREWALL", format="html"))

    html_empty = "" # Empty slot or description

    # 2. Multiples (Row 2) - PE/PB/PS
    anchor = v.get('anchor_metric', 'PE')
    
    # PE
    raw_pe = v.get('pe_ttm')
    raw_pe_static = v.get('pe_static')
    pe_display = "-"
    if raw_pe is not None:
         pe_display = f"{float(raw_pe):.1f}"
         if raw_pe_static is not None:
              try:
                  if round(float(raw_pe), 1) != round(float(raw_pe_static), 1):
                      pe_display += f' <small style="color:#6b7280;">({float(raw_pe_static):.1f})</small>'
              except: pass
    elif raw_pe_static is not None: pe_display = f"{float(raw_pe_static):.1f} (Static)"

    pe_label = "市盈率 (PE TTM/PE)" + (" ⚓" if anchor == 'PE' else "")
    html_pe = _get_metric_html_string(pe_label, pe_display, help_text="市盈率 (P/E Ratio)：衡量每 1 元净利润所支付的价格。反映投资回收期及市场对未来增长的预期。TTM (Trailing Twelve Months) 基于前四个季度动态滚动，Static 基于最新财年静态数据。适用于盈利稳定的企业。")

    # PB
    raw_pb = v.get('pb')
    pb_display = f"{float(raw_pb):.2f}" if raw_pb is not None else "-"
    pb_label = "市净率 (PB Ratio)" + (" ⚓" if anchor == 'PB' else "")
    html_pb = _get_metric_html_string(pb_label, pb_display, help_text="市净率 (P/B Ratio)：衡量每 1 元账面资产所支付的价格。反映了清算价值和资产溢价。适用于银行、地产等重资产行业，或盈利剧烈波动但净资产稳定的企业。")

    # PS
    raw_ps = v.get('ps') or v.get('ps_ttm')
    if raw_ps is None and anchor == 'PS': raw_ps = v.get('current_val')
    ps_display = f"{float(raw_ps):.2f}" if raw_ps is not None else "-"
    ps_label = "市销率 (PS Ratio)" + (" ⚓" if anchor == 'PS' else "")
    html_ps = _get_metric_html_string(ps_label, ps_display, help_text="市销率 (P/S Ratio)：衡量每 1 元营业收入所支付的价格。由于营收难以在该环节造假，该指标对高增长初创期或研发投入巨大的未盈利企业具有极高的估值锚点价值。")
    
    # --- Fullscreen Dialog Definition ---
    @st.dialog("📈 估值对标全屏分析", width="large")
    def show_valuation_fullscreen():
        st.markdown(f"### {data.symbol_name or data.symbol} - 历史估值走势图")
        render_valuation_chart_content(data, chart_start_date, chart_end_date)
        st.markdown("---")
        st.caption("提示：您可以利用 Plotly 工具栏进行局部放大、下载图片或重置坐标轴。")

    # --- Unified Render ---
    v_sep = '<div style="position:absolute; right:0; top:15%; height:70%; width:1px; background:rgba(255,255,255,0.1);"></div>'
    
    # Use native st.container(border=True) which we styled via CSS
    with st.container(border=True):
        # Header (Unified look with Section 2)
        st.markdown(clean_html(f"""
        <div class="vera-card-header">
            <span style="font-weight:700; color:#e2e8f0; font-size:0.9rem;">2. 价值评估 (Valuation)</span>
        </div>
        """), unsafe_allow_html=True)
        
        # Row 1
        st.markdown('<div style="height: 12px;"></div>', unsafe_allow_html=True) # Buffer
        r1c1, r1c2, r1c3 = st.columns([1, 1, 1], gap="large")
        with r1c1:
            st.markdown(clean_html(f'<div style="padding-left: 24px; position:relative;">{html_status}{v_sep}</div>'), unsafe_allow_html=True)
        with r1c2:
            st.markdown(clean_html(f'<div style="position:relative;">{html_quality}{v_sep}</div>'), unsafe_allow_html=True)
        with r1c3:
            st.markdown(clean_html(f'<div style="padding-right: 24px;">{html_empty}</div>'), unsafe_allow_html=True)
        
        st.markdown('<div style="height:32px;"></div>', unsafe_allow_html=True)
        
        # Row 2
        r2c1, r2c2, r2c3 = st.columns([1, 1, 1], gap="large")
        with r2c1:
            st.markdown(clean_html(f'<div style="padding-left: 24px; position:relative; margin-bottom:12px;">{html_pe}{v_sep}</div>'), unsafe_allow_html=True)
        with r2c2:
            st.markdown(clean_html(f'<div style="position:relative;">{html_pb}{v_sep}</div>'), unsafe_allow_html=True)
        with r2c3:
            st.markdown(clean_html(f'<div style="padding-right: 24px;">{html_ps}</div>'), unsafe_allow_html=True)
            
        st.markdown('<div style="height:12px;"></div>', unsafe_allow_html=True)
        
        # Row 3: Full-width expander for chart
        st.markdown('<div style="margin: 0 24px;">', unsafe_allow_html=True)
        exp = st.expander("📊 股价vsPE历史走势", expanded=False)
        with exp:
             # Header with fullscreen button
             ec1, ec2 = st.columns([4, 1])
             with ec1:
                  st.caption("该图表展示了过去 10 年的股价运行区间与 PE 估值波动对标。")
             with ec2:
                  if st.button("🖼️ 全屏对话框查看", use_container_width=True, key="val_fullscreen_btn"):
                       show_valuation_fullscreen()
             
             render_valuation_chart_content(data, chart_start_date, chart_end_date)
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<div style="height:24px;"></div>', unsafe_allow_html=True) # Bottom buffer


def render_behavior_and_cognition(data: DashboardData, profile: Optional[RiskProfile] = None):
    section_title("5. 行为与认知 (Behavior & Cognition)")
    c1, c2, c3 = st.columns(3)
    
    # Column 1: 行为建议 (Actionable)
    with c1:
        st.info(f"**行为建议**\n\n{data.behavior_suggestion or '暂无建议'}")
    
    # Column 2: 认知预警 (Cognitive Warning)
    with c2:
        # Use detect_risk_combination for dynamic warning
        risk_alert = detect_risk_combination(data, profile)
        if risk_alert:
            risk_level, risk_title, risk_message = risk_alert
            if risk_level == "极高":
                st.error(f"**{risk_title}**\n\n{risk_message}")
            elif risk_level == "高":
                st.warning(f"**{risk_title}**\n\n{risk_message}")
            else:
                st.info(f"**{risk_title}**\n\n{risk_message}")
        else:
            msg = data.cognitive_warning or "当前暂无特定认知预警。"
            st.info(f"**认知预警**\n\n{msg}")
    
    # Column 3: 风险画像匹配 / 关键护栏
    with c3:
        flags = data.behavior_flags or []
        if flags:
            st.markdown("**关键护栏**")
            for f in flags[:2]:  # Show max 2 flags
                level = f.get('flag_level', 'INFO')
                icon = "🚨" if level == "ALERT" else "⚠️" if level == "WARN" else "ℹ️"
                st.caption(f"{icon} {f.get('flag_title')}")
        else:
            if profile:
                level_map = {"CONSERVATIVE": "保守型", "BALANCED": "均衡型", "AGGRESSIVE": "进取型"}
                level_cn = level_map.get(profile.risk_tolerance_level, profile.risk_tolerance_level)
                st.info(f"**风险画像**: {level_cn}\n\n当前展示参数已匹配您的风险偏好。")
            else:
                st.caption("无特殊风险护栏触发")


# --- Expert Mode (Expert Mode UI Partition) ---

def render_expert_audit_panel(data: DashboardData):
    """
    渲染专家模式审计面板 (Expert Audit Panel)
    """
    audit = data.expert_audit
    if not audit:
        st.warning("当前资产暂无专家审计数据。")
        return

    st.markdown("""
    <div style="
        border-left: 4px solid #3b82f6;
        padding-left: 16px;
        margin: 40px 0 20px 0;
        background: rgba(59, 130, 246, 0.05);
        padding-top: 8px;
        padding-bottom: 8px;
        border-radius: 0 8px 8px 0;
    ">
        <div style="font-size:1.2rem; font-weight:700; color:#3b82f6;">🔬 专家审计视图 (Expert Audit Insight)</div>
        <div style="font-size:0.8rem; color:#64748b;">本视图仅供专业投研人员复核模型逻辑边界使用，不作为交易指令。</div>
    </div>
    """, unsafe_allow_html=True)
    
    # --- Expert Enhancement Options (Restored from old Sidebar location) ---
    with st.expander("🛠️ 专家增强项 (Expert Enhancements)", expanded=False):
        exc1, exc2 = st.columns(2)
        with exc1:
            show_debug = st.checkbox("📊 显示底层报文 (Debug JSON)", value=False, key="expert_debug_json")
            if show_debug:
                st.json(audit)
        with exc2:
            if st.button("⚡ 强制刷新载荷 (Force Reload)", use_container_width=True):
                st.cache_data.clear()
                st.rerun()
    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

    # UI Partition: 4 Blocks
    
    # 1. Overview & Path (Columns)
    c1, c2 = st.columns([1, 1], gap="large")
    
    with c1:
        st.markdown('<div class="vera-card" style="padding:20px; height:100%;">', unsafe_allow_html=True)
        st.markdown('<div style="font-size:0.85rem; font-weight:700; color:#64748b; margin-bottom:12px;">① 状态总览 (Status Overview)</div>', unsafe_allow_html=True)
        
        state_info = audit.get("state", {})
        sig = audit.get("price_signal", {})
        
        st.markdown(f"""
        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:16px;">
            <div>
                <p style="margin:0; font-size:0.75rem; color:#94a3b8;">D-State / I-State</p>
                <p style="margin:0; font-size:1.1rem; font-weight:700; color:#f1f5f9;">{state_info.get('d_state')} / {state_info.get('i_state')}</p>
                <p style="margin:0; font-size:0.85rem; color:#64748b;">{state_info.get('label')}</p>
            </div>
            <div>
                <p style="margin:0; font-size:0.75rem; color:#94a3b8;">判定置信度 (Confidence)</p>
                <p style="margin:0; font-size:1.1rem; font-weight:700; color:#22c55e;">{sig.get('confidence', 0.0)*100:.0f}%</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown(f'<div style="margin-top:16px; padding:10px; background:rgba(59,130,246,0.1); border-radius:6px; font-size:0.85rem; color:#3b82f6;">信号状态: <b>{sig.get("status")}</b></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with c2:
        st.markdown('<div class="vera-card" style="padding:20px; height:100%;">', unsafe_allow_html=True)
        st.markdown('<div style="font-size:0.85rem; font-weight:700; color:#64748b; margin-bottom:12px;">② 状态迁移路径 (Path History)</div>', unsafe_allow_html=True)
        
        history = audit.get("transition_path", [])
        if history:
            path_html = ""
            for h in history:
                color = "#3b82f6" if h.get("confirmed") else "#94a3b8"
                path_html += f'<div style="display:flex; justify-content:space-between; margin-bottom:4px; font-size:0.8rem; font-family:monospace;">'
                path_html += f'<span style="color:#64748b;">{h.get("t")}</span>'
                path_html += f'<span style="color:{color}; font-weight:700;">{h.get("d_state")}</span>'
                path_html += f'</div>'
            st.markdown(path_html, unsafe_allow_html=True)
        else:
            st.caption("暂无历史迁移记录")
        st.markdown('</div>', unsafe_allow_html=True)

    # 2. Evidence & Counter-Evidence
    e1, e2 = st.columns([1, 1], gap="large")
    
    with e1:
        st.markdown('<div class="vera-card" style="padding:20px; height:100%;">', unsafe_allow_html=True)
        st.markdown('<div style="font-size:0.85rem; font-weight:700; color:#64748b; margin-bottom:12px;">③ 判定依据 (Direct Evidence)</div>', unsafe_allow_html=True)
        
        evidence = audit.get("evidence", [])
        for e in evidence:
            val_icon = "🔵" if e.get("value") else "⚪"
            st.markdown(f"""
            <div style="margin-bottom:12px;">
                <div style="font-size:0.9rem; color:#e2e8f0;">{val_icon} {e.get('label')}</div>
            """, unsafe_allow_html=True)
            m = e.get("metric")
            if m:
                st.markdown(f' <div style="font-size:0.75rem; color:#64748b; margin-left:24px;">{m["name"]}: <b>{m["value"]}</b> (阈值: {m["threshold"]})</div>', unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with e2:
        st.markdown('<div class="vera-card" style="padding:20px; height:100%;">', unsafe_allow_html=True)
        st.markdown('<div style="font-size:0.85rem; font-weight:700; color:#64748b; margin-bottom:12px;">④ 反证审计清单 (Counter Evidence)</div>', unsafe_allow_html=True)
        
        checklist = audit.get("counter_evidence_checklist", {})
        st.markdown(f'<div style="font-size:0.95rem; font-weight:700; color:#f1f5f9; margin-bottom:4px;">{checklist.get("title")}</div>', unsafe_allow_html=True)
        st.markdown(f'<div style="font-size:0.75rem; color:#64748b; margin-bottom:12px;">{checklist.get("subtitle")}</div>', unsafe_allow_html=True)
        
        items = checklist.get("items", [])
        checked_count = 0
        for item in items:
            key = f"ce_{checklist.get('state')}_{item['id']}_ui"
            # Using st.checkbox for interaction as per user request
            if st.checkbox(item["label"], key=key, help=item.get("definition")):
                checked_count += 1
        
        rules = checklist.get("rules", {})
        threshold = rules.get("boundary_threshold", 2)
        if checked_count >= threshold:
            st.warning(rules.get("boundary_warning", "当前状态可能处于边界区域，模型置信度下降。"))
        
        st.markdown('</div>', unsafe_allow_html=True)


def render_verdict(data: DashboardData):
    """🧠 Verdict：最后、唯一允许综合"""
    section_title("🧠 VERA Verdict (综合裁定)")
    summary = data.overall_conclusion or "无综合裁定"
    st.markdown(f"<div class='vera-verdict'>{summary}</div>", unsafe_allow_html=True)

def render_page(data: DashboardData, profile: Optional[RiskProfile] = None, chart_start_date=None, chart_end_date=None):
    """
    Streamlit Layout - Final Version
    
    Structure:
    A. Header (with Expert Toggle)
    B. Top Decision Area (2 rows)
       - Row 1: Position Quadrant + Cognitive Warning + Behavior Flags (3 columns)
       - Row 2: VERA Verdict (full width)
    C. Risk Overlay (3 columns: Asset / Sector / Market)
    D. Deep Dive (3 columns)
    E. Valuation (3 columns)
    F. Quality Overlay (expandable)
    G. Behavior & Cognition (3 columns)
    """
    # Expert Mode status notification (toast)
    expert_mode = st.session_state.get("expert_mode_active", False)
    if expert_mode and "last_expert_mode" not in st.session_state:
        st.session_state.last_expert_mode = True
        st.toast("🕵️ 正在进入专家审计视图...", icon="🔬")
    elif not expert_mode and "last_expert_mode" in st.session_state:
        del st.session_state.last_expert_mode

    st.sidebar.markdown("---")

    # Detect Index
    is_index = False
    index_role = None
    if hasattr(data, 'overlay') and data.overlay:
        is_index = data.overlay.get('asset_type') == 'INDEX'
        index_role = data.overlay.get('index_role')

    # A. Header
    if expert_mode:
        st.markdown('<div class="expert-overlay-active" style="position:fixed; top:0; left:0; width:100%; height:100%; pointer-events:none; z-index:9999; border: 4px solid #3b82f6; opacity:0.1; box-sizing:border-box;"></div>', unsafe_allow_html=True)
    
    render_header(data, is_index, index_role, expert_mode=expert_mode)

    # A. Header (Force Banner if Expert Mode)
    if expert_mode:
        st.markdown('<div class="expert-overlay-border"></div>', unsafe_allow_html=True)
        st.markdown("""
        <div class="expert-mode-banner">
            <div style="display:flex; align-items:center; gap:16px;">
                <div style="font-size:1.8rem; filter: drop-shadow(0 0 5px white);">🕵️</div>
                <div>
                    <span style="font-size:1.1rem; font-weight:800; letter-spacing:0.03em;">专家审计展示模式已激活 (EXPERT MODE)</span><br/>
                    <span style="font-size:0.8rem; opacity:0.8; font-weight:400;">底层判定依据已穿透注入核心指标卡片，并在首页顶部显示完整审计工作台。</span>
                </div>
            </div>
            <div style="text-align:right;">
                <span style="background:rgba(255,255,255,0.2); color:white; padding:4px 12px; border-radius:20px; font-size:0.7rem; font-weight:700;">AUDIT PROTECTED</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # MOVE Audit panel to the VERY TOP when expert mode is on
        if data.expert_audit:
            render_expert_audit_panel(data)
            st.markdown("---")
        else:
            st.info("💡 专家模型已开启，但由于部分审计原始指标缺失，无法构建完整的逻辑路径载荷。请尝试评估 TSLA 或 NVDA 查看完整效果。")

    # render_header removed here as it is called above

    # --- Sidebar: Diagnosis ---
    if expert_mode and st.sidebar.checkbox("🛠️ 调试：查看审计报文"):
        st.sidebar.json(data.expert_audit)

    # B. Top Decision Area (VERA)
    
    vera_result = None
    try:
        from vera.interface import get_vera_verdict
        with st.spinner("Running VERA Engines..."):
             # Use session_state to ensure we get the user-selected date correctly across scopes
             vera_result = get_vera_verdict(data.symbol, anchor_date=st.session_state.get("eval_date"))
        
        render_vera_top_decision_area(vera_result)
        
    except Exception as e:
        st.error(f"VERA Engine Error: {e}")
        # st.exception(e) # Debug


    # C. Supplementary Indicators (Legacy Top Area)
    # section_title("📊 辅助指标 (Supplementary Indicators)")
    
    # B.1 Row 1: Position Quadrant + Cognitive + Behavior (3 columns)
    # B.1 Unified Supplementary Card
    render_supplementary_card(data, profile, vera_result)
    
    # B.2 Row 2: VERA Verdict (Full Width) -> Removed as replaced by VERA above
    # B.2 Row 2: VERA Verdict (Three Column Layout)
    # st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)
    # vc1, vc2, vc3 = st.columns(3)
    # with vc1:
    #    render_verdict(data)
    
    
    
    # C. Risk Overlay (Unified Card)
    render_risk_overlay(data, vera_result, expert_mode=expert_mode)
    
    # D. Valuation (Unified Card)
    render_valuation_card(data, chart_start_date=chart_start_date, chart_end_date=chart_end_date)
    
    # E. Quality & Profitability Filter (Universal for all strategies)
    render_quality_card(data)
    
    # NEW: AI CapEx Risk Overlay
    render_ai_capex_card(data)
    
    # NEW: CSP Strategy Evaluation
    render_csp_eval_card(data, vera_result, expert_mode=expert_mode)
    
    # G. Behavior & Cognition (Unified Card)
    render_behavior_card(data, profile)

    st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)




def render_asset_management():
    st.title("⚙️ 资产管理 (Asset Universe Management)")
    
    # 1. Fetch current universe
    # FORCE RELOAD to ensure new columns are picked up
    import importlib
    import engine.universe_manager
    importlib.reload(engine.universe_manager)
    from engine.universe_manager import get_universe_assets_v2
    
    universe_data = get_universe_assets_v2()
    if not universe_data:
        st.info("自选池为空，请在下方添加新标的。")
        df_universe = pd.DataFrame(columns=[
            "asset_id", "symbol_name", "asset_type", "market", 
            "scheme", "sector_name", "industry_name", 
            "benchmark_etf", "benchmark_index",
            "last_data_date", "data_duration_years",
            "last_report_date", "report_duration_years"
        ])
    else:
        df_universe = pd.DataFrame(universe_data)
        
        # Ensure all columns exist and screen for desired order
        desired_cols = [
            "asset_id", "symbol_name", "asset_type", "market", 
            "scheme", "sector_name", "industry_name", 
            "benchmark_etf", "benchmark_index",
            "last_data_date", "data_duration_years",
            "last_report_date", "report_duration_years"
        ]
        # Reindex to ensure order and fill missing with NaN if any
        df_universe = df_universe.reindex(columns=desired_cols)
        
        # --- Apply Strict Sorting Rules ---
        def get_df_sort_key(row):
            m = row['market']
            t = row['asset_type']
            s = row['asset_id']
            
            # Market Priority: HK(0) > US(1) > CN(2)
            m_o = 3
            if m == 'HK': m_o = 0
            elif m == 'US': m_o = 1
            elif m == 'CN': m_o = 2
            
            # Type Priority: EQUITY(0) > ETF(1) > INDEX(2)
            t_o = 3
            if t in ['EQUITY', 'STOCK']: t_o = 0  # 个股优先
            elif t == 'ETF': t_o = 1              # ETF次之
            elif t == 'INDEX': t_o = 2            # 指数最后
            
            # Numeric Sort for codes
            import re
            d = re.findall(r'\d+', s)
            if d:
                code_part = d[-1]
                if m == 'HK': code_part = code_part.zfill(5)
                try: return (m_o, t_o, 0, int(code_part))
                except: pass
            return (m_o, t_o, 1, s.upper())

        df_universe['sort_key'] = df_universe.apply(get_df_sort_key, axis=1)
        df_universe = df_universe.sort_values(by='sort_key').drop(columns=['sort_key'])

        # Standardize type for display (STOCK -> EQUITY)
        if 'asset_type' in df_universe.columns:
             df_universe['asset_type'] = df_universe['asset_type'].replace('STOCK', 'EQUITY')

        # --- Transform for Display (N/A for Non-Equity) ---
        def format_report_duration(row):
            if row['asset_type'] in ['ETF', 'INDEX']:
                return "N/A"
            val = row['report_duration_years']
            if pd.isna(val) or val == 0: return "0.00 年"
            try:
                return f"{float(val):.2f} 年"
            except:
                return str(val)

        def format_report_date(row):
            if row['asset_type'] in ['ETF', 'INDEX']:
                return "N/A"
            val = row['last_report_date']
            if pd.isna(val) or val == "" or val == "None": return "None"
            return str(val)

        df_universe['report_duration_years'] = df_universe.apply(format_report_duration, axis=1)
        df_universe['last_report_date'] = df_universe.apply(format_report_date, axis=1)

        # Final Column Ordering
        cols = [
            "primary_symbol", "asset_id", "symbol_name", "asset_type", "market", "tags", 
            "scheme", "sector_code", "sector_name", "industry_code", "industry_name", 
            "benchmark_etf", "benchmark_index",
            "last_data_date", "data_duration_years",
            "last_report_date", "report_duration_years"
        ]
        for c in cols:
            if c not in df_universe.columns: df_universe[c] = ""
        df_universe = df_universe[cols]

    # --- Dedicated Registration Form ---
    # --- Dedicated Registration Form ---
    # --- Dedicated Registration Form ---
    st.subheader("➕ 注册新资产 (Register New Asset)")
    with st.expander("点击展开注册表单", expanded=True):
        from engine.asset_resolver import resolve_asset
        from utils.stock_name_fetcher import get_stock_name
        
        # Row 1: Basic Info
        reg_col1, reg_col2, reg_col3, reg_col4 = st.columns([1.5, 2, 1, 1])
        with reg_col1:
            new_sym = st.text_input("输入标的代码", placeholder="例如: 700, 3690, TSLA", help="输入代码后, 下方类型和市场会自动预判", key="reg_symbol")
        
        # Pre-resolve for defaults
        default_type = "EQUITY"
        default_market = "US"
        if new_sym:
            try:
                info = resolve_asset(new_sym)
                default_type = info.asset_type
                default_market = info.market
            except:
                pass
        
        with reg_col2:
            new_name = st.text_input("资产名称 (可选)", placeholder="自动获取或手动输入")
        ALL_TYPES = ["EQUITY", "ETF", "INDEX", "CRYPTO", "TRUST"]
        try:
             def_idx = ALL_TYPES.index(default_type)
        except ValueError:
             def_idx = 0

        with reg_col3:
            final_type = st.selectbox("类型", options=ALL_TYPES, index=def_idx)
        with reg_col4:
            final_market = st.selectbox("市场", options=["US", "HK", "CN"], index=["US", "HK", "CN"].index(default_market))

        # --- Row 2: Classification Details ---
        st.markdown("###### 🗂️ 分类信息 (Classification)")
        class_col1, class_col2, class_col3 = st.columns(3)
        with class_col1:
            new_scheme = st.text_input("分类体系 (Scheme)", value="GICS", placeholder="GICS, SW, etc.")
        with class_col2:
            new_sector = st.text_input("板块名称 (Sector Name)", placeholder="Technology, Consumer Discretionary")
        with class_col3:
            new_industry = st.text_input("行业名称 (Industry Name)", placeholder="Software, Automobiles")

        # --- Row 3: Codes & Benchmarks ---
        st.markdown("###### 📊 代码与对标 (Codes & Benchmarks)")
        meta_col1, meta_col2, meta_col3, meta_col4 = st.columns(4)
        with meta_col1:
            new_sector_code = st.text_input("板块代码 (Sector Code)", placeholder="Optional")
        with meta_col2:
            new_industry_code = st.text_input("行业代码 (Industry Code)", placeholder="Optional")
        with meta_col3:
            new_bench_etf = st.text_input("对标 ETF", placeholder="SPY, QQQ")
        with meta_col4:
            new_bench_idx = st.text_input("对标指数", placeholder="^GSPC, ^NDX")

        # --- Row 4: Tags ---
        st.markdown("###### 🏷️ 标签 (Tags)")
        new_tags = st.text_input("标签 (用逗号分隔)", placeholder="HYPERSCALER, AI_INFRA_CORE, etc.")

        # --- Action Button ---
        st.markdown("<br>", unsafe_allow_html=True)
        # Shortened Button Width (Centered)
        _, btn_col, _ = st.columns([1, 1, 1])
        with btn_col:
            if st.button("➕ 确认注册 (Confirm Register)", type="primary", use_container_width=True):
                if not new_sym:
                    st.error("请输入代码")
                else:
                    try:
                        from engine.universe_manager import add_to_universe
                        
                        resolved_name = new_name or get_stock_name(new_sym)
                        
                        add_to_universe(
                            raw_symbol=new_sym,
                            name=resolved_name,
                            market=final_market,
                            asset_type=final_type,
                            scheme=new_scheme,
                            sector_name=new_sector if new_sector else None,
                            sector_code=new_sector_code if new_sector_code else None,
                            industry_name=new_industry if new_industry else None,
                            industry_code=new_industry_code if new_industry_code else None,
                            benchmark_etf=new_bench_etf if new_bench_etf else None,
                            benchmark_index=new_bench_idx if new_bench_idx else None,
                            tags=new_tags if new_tags else None
                        )
                        st.success(f"✅ {new_sym} ({final_market}|{final_type}) 已成功加入资产池。")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ 注册失败: {e}")

    st.subheader("📋 现有资产一览表")
    edited_data = st.data_editor(
        df_universe, 
        key="universe_editor_final_fixed_v2", 
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "primary_symbol": st.column_config.TextColumn("输入代码", help="原始代码 (如 700, 3690)"),
            "asset_id": st.column_config.TextColumn("典范代码", help="标准化 ID", disabled=True),
            "symbol_name": st.column_config.TextColumn("名称"),
            "asset_type": st.column_config.SelectboxColumn("类型", options=["EQUITY", "ETF", "INDEX", "CRYPTO", "TRUST"]),
            "market": st.column_config.SelectboxColumn("市场", options=["US", "HK", "CN"]),
            "tags": st.column_config.TextColumn("标签 (Tags)", help="用于策略标记，如 HYPERSCALER"),
            "scheme": st.column_config.TextColumn("分类体系"),
            "sector_code": st.column_config.TextColumn("板块代码"),
            "sector_name": st.column_config.TextColumn("板块名称"),
            "industry_code": st.column_config.TextColumn("行业代码"),
            "industry_name": st.column_config.TextColumn("行业名称"),
            "benchmark_etf": st.column_config.TextColumn("对标ETF"),
            "benchmark_index": st.column_config.TextColumn("对标指数"),
            "last_data_date": st.column_config.TextColumn("最新行情日期", help="Latest Price Date", disabled=True),
            "data_duration_years": st.column_config.NumberColumn("行情时长", help="Price Duration (Years)", disabled=True, format="%.2f 年"),
            "last_report_date": st.column_config.TextColumn("财报日期", help="Latest Financial Report Date", disabled=True),
            "report_duration_years": st.column_config.TextColumn("财报年限", help="Financial History Duration (Years)", disabled=True)
        }
    )

    # Shortened Save Button Width (Centered)
    _, save_btn_col, _ = st.columns([1, 1, 1])
    with save_btn_col:
        if st.button("💾 保存表格所有修改", type="primary", use_container_width=True):
            # 1. Access the state of data_editor
            state = st.session_state.get("universe_editor_final_fixed_v2", {})
            edited = state.get("edited_rows", {})
            added = state.get("added_rows", [])
            deleted = state.get("deleted_rows", [])

            if not edited and not added and not deleted:
                st.info("没有检测到任何修改。")
            else:
                # 3. Execution
                try:
                    from engine.universe_manager import add_to_universe
                    
                    def _sanitize(val):
                        if val is None: return None
                        s = str(val).strip()
                        if s.endswith(".0"): return s[:-2]
                        return s

                    # Handle deletions - actually DELETE from database
                    for row_idx in deleted:
                        asset_id = df_universe.iloc[row_idx]["asset_id"]
                        conn_del = get_connection()
                        try:
                            cursor = conn_del.cursor()
                            # Permanently delete from all related tables
                            cursor.execute("DELETE FROM asset_universe WHERE asset_id = ?", (asset_id,))
                            cursor.execute("DELETE FROM asset_classification WHERE asset_id = ?", (asset_id,))
                            cursor.execute("DELETE FROM asset_symbol_map WHERE asset_id = ?", (asset_id,))
                            cursor.execute("DELETE FROM assets WHERE asset_id = ?", (asset_id,))
                            conn_del.commit()
                        except Exception as e:
                            st.error(f"Failed to delete {asset_id}: {e}")
                            conn_del.rollback()
                        finally:
                            conn_del.close()

                    # Handle edits
                    for row_idx, changes in edited.items():
                        # Fetch original data for the row
                        original = df_universe.iloc[row_idx]
                        asset_id = original["asset_id"]
                        
                        # Merge changes into a clean dict
                        updated_vals = {}
                        for key in ["symbol_name", "market", "asset_type", "tags", "scheme", 
                                    "sector_code", "sector_name", "industry_code", "industry_name",
                                    "benchmark_etf", "benchmark_index"]:
                            if key in changes:
                                updated_vals[key] = _sanitize(changes[key])
                            else:
                                updated_vals[key] = _sanitize(original.get(key))
                        
                        # Update using add_to_universe logic (which handles updates)
                        add_to_universe(
                            raw_symbol=asset_id, # Use asset_id as symbol to locate
                            name=updated_vals["symbol_name"],
                            market=updated_vals["market"],
                            asset_type=updated_vals["asset_type"],
                            tags=updated_vals["tags"],
                            scheme=updated_vals["scheme"],
                            sector_code=updated_vals["sector_code"],
                            sector_name=updated_vals["sector_name"],
                            industry_code=updated_vals["industry_code"],
                            industry_name=updated_vals["industry_name"],
                            benchmark_etf=updated_vals["benchmark_etf"],
                            benchmark_index=updated_vals["benchmark_index"]
                        )

                    # Handle additions (New Rows)
                    for new_row in added:
                        s = _sanitize(new_row.get("primary_symbol"))
                        if not s: continue # Skip empty
                        
                        add_to_universe(
                            raw_symbol=s,
                            name=_sanitize(new_row.get("symbol_name")),
                            market=_sanitize(new_row.get("market", "US")),
                            asset_type=_sanitize(new_row.get("asset_type", "EQUITY")),
                            tags=_sanitize(new_row.get("tags")),
                            scheme=_sanitize(new_row.get("scheme", "GICS")),
                            sector_code=_sanitize(new_row.get("sector_code")),
                            sector_name=_sanitize(new_row.get("sector_name")),
                            industry_code=_sanitize(new_row.get("industry_code")),
                            industry_name=_sanitize(new_row.get("industry_name")),
                            benchmark_etf=_sanitize(new_row.get("benchmark_etf")),
                            benchmark_index=_sanitize(new_row.get("benchmark_index"))
                        )

                    st.success("✅ 修改已保存 (Saved Successfully)")
                    st.rerun()

                except Exception as e:
                    st.error(f"❌ 保存失败: {e}")

    st.markdown("---")
    st.markdown("---")
    
    # 恢复表外删除功能
    with st.expander("🗑️ 删除资产 (Delete Asset)", expanded=False):
        c_del1, c_del2 = st.columns([3, 1])
        with c_del1:
            all_assets = df_universe["asset_id"].tolist() if not df_universe.empty else []
            # Combobox allows searching
            asset_to_delete = st.selectbox(
                "选择要删除的资产", 
                options=[""] + all_assets, 
                format_func=lambda x: f"{x} ({df_universe[df_universe['asset_id']==x]['symbol_name'].values[0]})" if x in all_assets else "请选择..."
            )
        with c_del2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🗑️ 确认删除", type="primary"):
                if not asset_to_delete:
                    st.error("请先选择资产")
                else:
                    try:
                         # Use existing deletion logic
                         from engine.universe_manager import remove_from_universe
                         # Actually we defined a local helper in save logic, but better import or query DB
                         # Just use SQL delete for consistency with Save logic which deletes from table
                         conn_del = get_connection()
                         cursor = conn_del.cursor()
                         cursor.execute("DELETE FROM asset_universe WHERE asset_id = ?", (asset_to_delete,))
                         cursor.execute("DELETE FROM asset_classification WHERE asset_id = ?", (asset_to_delete,))
                         conn_del.commit()
                         conn_del.close()
                         
                         st.success(f"✅ {asset_to_delete} 已删除。")
                         st.rerun()
                    except Exception as e:
                         st.error(f"❌ 删除失败: {e}")

def render_welcome():
    # --- Helper: Load Image as Base64 ---
    import base64
    import os
    
    def get_img_as_base64(file_path):
        try:
            with open(file_path, "rb") as f:
                data = f.read()
            return base64.b64encode(data).decode()
        except:
            return ""

    banner_b64 = get_img_as_base64("assets/welcome_banner_new.jpg")
    
    # --- CSS Styles ---
    st.markdown(f"""
    <style>
    /* Global Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    
    /* Reduce Streamlit's default top padding */
    .block-container {{
        padding-top: 2rem !important;
        margin-top: -3rem !important;
    }}
    
    .vera-card {{
        background-color: #1e1e1e;
        border: 1px solid #333;
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 24px;
        height: 100%;
        transition: transform 0.2s;
    }}
    .vera-card:hover {{
        transform: translateY(-2px);
        border-color: #555;
    }}
    
    /* Hero Section */
    .hero-card {{
        background-color: #0f1115;
        /* Gradient handled in inline style now, but keeping this for fallback/reference */
        border: 1px solid #333;
        border-radius: 16px;
        padding: 60px 48px;
        text-align: left;
        margin-bottom: 32px;
        position: relative;
        overflow: hidden;
        min-height: 480px; 
        display: flex;
        flex-direction: column;
        justify-content: center;
    }}
    .hero-tag {{
        color: rgba(252, 211, 77, 0.8); /* Weaker Gold */
        font-size: 12px; 
        letter-spacing: 2px; 
        margin-bottom: 12px; 
        font-weight: 600; 
        text-transform: uppercase;
    }}
    .hero-title {{
        font-size: 36px; 
        font-weight: 700; 
        color: rgba(255, 255, 255, 0.9); /* Reset to White */
        margin-bottom: 16px;
        line-height: 1.2;
    }}
    .hero-subtitle-cn {{
        font-size: 16px;  /* Reduced from 20px */
        color: rgba(209, 213, 219, 0.8); /* More transparent gray */
        margin-bottom: 24px; 
        font-weight: 400;
    }}
    .hero-desc {{
        font-size: 14px;
        color: #9ca3af;
        margin-bottom: 32px;
        max-width: 600px;
        line-height: 1.6;
    }}
    
    /* Red Button Style (Visual Link) */
    /* Red Button Style (Visual Link) */
    .hero-btn, .hero-btn:visited, .hero-btn:active {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        background-color: #ff4b4b; /* Red */
        color: #ffffff !important;
        font-weight: 600;
        padding: 10px 24px;
        border-radius: 6px;
        text-decoration: none !important;
        transition: background-color 0.2s, color 0.2s;
        width: fit-content;
        font-size: 14px;
    }}
    .hero-btn:hover {{
        background-color: #ff3333;
        color: #ffff00 !important; /* Yellow on hover */
        text-decoration: none !important;
    }}

    /* Get Started Steps & CTA */
    .step-item {{
        display: flex;
        align-items: flex-start;
        margin-bottom: 16px;
    }}
    .step-num {{
        background-color: #2D3748;
        color: #A0AEC0;
        width: 24px;
        height: 24px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: bold;
        font-size: 12px;
        margin-right: 12px;
        flex-shrink: 0;
        margin-top: 2px;
    }}
    .step-content {{
        font-size: 14px;
        color: #d1d5db;
        line-height: 1.5;
    }}
    .cta-card {{
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        margin-top: 20px;
        margin-bottom: 16px;
    }}
    .cta-title {{
        font-size: 16px;
        font-weight: 700;
        color: #fff;
        margin-bottom: 4px;
    }}
    .cta-text {{
        font-size: 13px;
        color: #9ca3af;
    }}
    
    /* Section Headers */
    .section-header {{
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 24px;
        font-size: 20px;
        font-weight: 700;
        color: #f3f4f6;
    }}
    .section-icon-box {{
        background-color: #2D3748;
        width: 36px;
        height: 36px;
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 18px;
    }}
    
    /* Framework Cards */
    .fw-icon {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 4px 8px;
        border-radius: 6px;
        color: #1a202c;
        font-weight: bold;
        font-size: 14px;
        margin-right: 8px;
    }}
    .fw-title {{
        font-size: 16px; 
        font-weight: 700; 
        color: #fff; 
        margin-bottom: 12px;
    }}
    .fw-list li {{
        margin-bottom: 8px;
        color: #d1d5db;
        font-size: 13px;
        line-height: 1.6;
    }}
    .fw-caption {{
        margin-top: 16px;
        font-size: 12px;
        color: #6b7280;
        font-style: italic;
    }}
    
    </style>
    """, unsafe_allow_html=True)

    # --- Hero Section HTML ---
    # Container for Image + Overlay
    # Use explicit dedent or just left-align string content to prevent Markdown Code Block interpretation
    st.markdown(f"""
<div style="position: relative; margin-bottom: 32px; border-radius: 16px; overflow: hidden;">
    <img src="data:image/jpeg;base64,{banner_b64}" style="width: 100%; height: auto; display: block;">
    <div style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; 
                background: linear-gradient(90deg, rgba(15, 17, 21, 0.90) 10%, rgba(15, 17, 21, 0.6) 35%, rgba(15, 17, 21, 0.0) 70%); 
                display: flex; flex-direction: column; justify-content: center; padding-left: 48px;">
        <div class="hero-tag">WELCOME TO VERA</div>
        <div class="hero-title">Intelligent Investment<br>Research System</div>
        <div class="hero-subtitle-cn">智能投研与风险评估系统</div>
        <a href="/?page=analysis" target="_self" class="hero-btn" style="margin-top: 12px;">
            开启新愿景 &nbsp; →
        </a>
    </div>
</div>
""", unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # --- Framework Section ---
    st.markdown("""
    <div class="section-header">
        <div class="section-icon-box">🍱</div>
        <div>核心框架 (VERA Framework)</div>
    </div>
    """, unsafe_allow_html=True)

    fc1, fc2 = st.columns(2)
    with fc1:
        st.markdown("""
        <div class="vera-card">
            <div class="fw-title">
                <span class="fw-icon" style="background-color: #F6E05E;">⚡</span>
                结构风险 · 你到底在扛什么风险？
            </div>
            <ul class="fw-list">
                <li>用 <strong style="color: #F6E05E;">D-State [D0-D6] + 最大回撤 + 波动率</strong> 描述风险阶段，而不是主观感觉。</li>
                <li>通过 <strong>Position & Risk Quadrant</strong> 把“贵不贵、顺不顺”映射到四个象限。</li>
            </ul>
            <div class="fw-caption">系统通过「资产分析 (Analysis)」页自动计算这些指标。</div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("""
        <div class="vera-card">
            <div class="fw-title">
                <span class="fw-icon" style="background-color: #68D391;">⚖️</span>
                估值锚点 · 这个价，值不值得去扛？
            </div>
            <ul class="fw-list">
                <li>使用历史估值带 (PE/PB Band) 而非单点市盈率。</li>
                <li>重点识别 Value Trap：看起来不贵，但与风险和质量不匹配。</li>
            </ul>
            <div class="fw-caption">在「Valuation」部分查看估值状态与锚点。</div>
        </div>
        """, unsafe_allow_html=True)
        
    with fc2:
        st.markdown("""
        <div class="vera-card">
            <div class="fw-title">
                <span class="fw-icon" style="background-color: #FC8181;">🛡️</span>
                质量缓冲 · 这家公司扛不扛得住？
            </div>
            <ul class="fw-list">
                <li>从 <strong>业务 / 财务 / 治理</strong> 三维评估能否扛住回撤，而不是只看一两个财务比率。</li>
                <li>缺失数据时按保守口径评估，避免给出过度乐观的质量判断。</li>
            </ul>
            <div class="fw-caption">通过「Quality Buffer」模块汇总 fundamentals 与分红数据。</div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("""
        <div class="vera-card">
            <div class="fw-title">
                <span class="fw-icon" style="background-color: #B794F4;">💡</span>
                行为与承受力 · 你能不能扛得住自己？
            </div>
            <ul class="fw-list">
                <li>行为标志和认知预警帮助识别追涨、恐慌等情绪化决策。</li>
                <li>当结构风险超出你的预设档位时，给出清晰提示。</li>
            </ul>
            <div class="fw-caption">结合「Risk Profile」与「Behavior & Cognition」区域使用。</div>
        </div>
        """, unsafe_allow_html=True)

    # --- Bottom Section: 1. Methodology Boundary (Left), 2. Get Started (Right) ---
    st.markdown("<br><br>", unsafe_allow_html=True)
    
    # Define two main columns for the bottom area
    col_methodology, col_start = st.columns([1, 1]) # Adjust ratio if needed (e.g. [1.2, 1])
    
    # --- Left Column: Methodology Boundary ---
    with col_methodology:
        st.markdown("""
        <div class="section-header">
            <div class="section-icon">⛔</div>
            <div>方法论边界 (Not Do)</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Original items were in 2 columns inside, now stack specific ones or keep grid?
        # Given wider column context vs half-page, stacking vertically might be better or 2-col mini grid.
        # User screenshot shows a list on the left. Let's stack them vertically or use a clean list.
        # Screenshot shows "x .. x .." vertical list.
        
        st.markdown('<div class="boundary-item">× &nbsp; 不预测短期涨跌，不给出“明天会上/下”的判断。</div>', unsafe_allow_html=True)
        st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)
        st.markdown('<div class="boundary-item">× &nbsp; 不做综合打分排行榜，避免把复杂风险简化成一个数字。</div>', unsafe_allow_html=True)
        st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)
        st.markdown('<div class="boundary-item">× &nbsp; 不设目标价，不提供“买入 / 卖出 / 加仓 / 清仓”指令。</div>', unsafe_allow_html=True)
        st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)
        st.markdown('<div class="boundary-item">× &nbsp; 不替你做决策，只帮你看清：你在承受什么，以及为此付出了什么价格。</div>', unsafe_allow_html=True)

    # --- Right Column: Get Started ---
    with col_start:
        st.markdown("""
        <div class="section-header">
            <div class="section-icon">🚀</div>
            <div>如何开始 (Get Started)</div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        <div class="step-item">
            <div class="step-num">1</div>
            <div class="step-content">
                <strong style="color:#e5e7eb">注册资产</strong><br>
                在 Universe 中配置关注资产与基准。
            </div>
        </div>
        <div class="step-item">
            <div class="step-num">2</div>
            <div class="step-content">
                <strong style="color:#e5e7eb">评估风险</strong><br>
                在 Analysis 查看结构风险、质量与估值。
            </div>
        </div>
        <div class="step-item">
            <div class="step-num">3</div>
            <div class="step-content">
                <strong style="color:#e5e7eb">辅助决策</strong><br>
                结合行为提示在 Verdict 中做出理性判断。
            </div>
        </div>
        """, unsafe_allow_html=True)
        
    
    # --- CTA Card (Centered) ---
    st.markdown("<br>", unsafe_allow_html=True)
    _, cta_col, _ = st.columns([1, 2, 1])
    with cta_col:
        st.markdown("""
        <div class="cta-card">
            <div style="font-size: 24px; margin-bottom: 8px;">✨</div>
            <div class="cta-title">Ready?</div>
            <div class="cta-text">开始您的第一次智能风险评估</div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("进入 Universe", type="primary", use_container_width=True):
             st.session_state.app_mode = "⚙️ 资产管理 (Universe)"
             st.rerun()

def render_risk_assessment_page():
    """🧘 Dedicated Risk Assessment Page / 专用风险自评页面"""
    st.markdown("# 🧘 风险承受力自评")
    st.markdown("### Risk Tolerance Self-Assessment")
    st.info("本问卷用于理解您对风险信息的心理承受方式，评估结果将影响 VERA 各模块的提示强度与解释风格。")
    
    active_profile = get_current_profile()
    if active_profile:
        level_map = {"CONSERVATIVE": "保守型", "BALANCED": "均衡型", "AGGRESSIVE": "进取型"}
        st.success(f"当前画像状态：**{level_map.get(active_profile.risk_tolerance_level, '已评估')}**")
    
    st.markdown("---")
    
    with st.form("risk_survey_full"):
        q1 = st.radio("Q1. 面对账户回撤（如下跌 15%）时的第一反应：", 
                      ["A. 明显不适，希望尽快了解风险是否继续扩大", "B. 可以接受，但需要知道逻辑是否恶化", "C. 视为常见波动，更关注长期位置"], index=1)
        q2 = st.radio("Q2. 您如何看待市场波动：", 
                      ["A. 波动本身是风险，会影响我的情绪和判断", "B. 波动值得关注，但只要逻辑在我就能坚持", "C. 波动是信息和机会，不是压力"], index=1)
        q3 = st.radio("Q3. 风险信息的呈现偏好：", 
                      ["A. 极度审慎，尽早、明确地进行风险提示", "B. 保持中性，在需要深入分析时展开", "C. 乐观主义，只在极端或系统性风险时提醒"], index=1)
        q4 = st.radio("Q4. 面对相互冲突的信号（如估值低但趋势差）时：", 
                      ["A. 宁可错过，也要明确提示“风险仍在”", "B. 兼听则明，同时展示正反两面信息", "C. 追求效率，简要说明风险但不反复强调"], index=1)
        q5 = st.radio("Q5. 您是否重视历史极端回撤的参考价值：", 
                      ["A. 是，我非常重视历史最差情况的重复可能性", "B. 视情况而定，作为参考之一", "C. 不是，我更看重资产当前的内生质量"], index=0)
        
        c1, c2 = st.columns([1, 4])
        with c1:
            submit = st.form_submit_button("保存评估结果", type="primary")
        with c2:
            if active_profile and st.form_submit_button("恢复系统默认"):
                reset_profile()
                st.rerun()
                
        if submit:
            def get_score(idx, text):
                if text.startswith("A"): return 0
                if text.startswith("B"): return 1
                return 2
            
            answers = {"Q1": q1, "Q2": q2, "Q3": q3, "Q4": q4, "Q5": q5}
            total_score = sum(get_score(k, v) for k, v in answers.items())
            save_user_profile(total_score, answers)
            st.success("画像已更新！正在重新应用系统参数...")
            st.rerun()

def render_data_import_page():
    """📥 Dedicated Data Import Page / 专用数据导入页面"""
    st.markdown("# 📥 历史数据管理")
    st.markdown("### Historical Data Management (CSV)")
    
    st.markdown("---")

    # 0. Configuration & Utilities Definition (Moved to top to prevent scope error)
    # Metric Mapper Utilities
    # 按照24个银行核心指标组织
    friendly_names = {
        # === 1. 资产负债表 (Balance Sheet - Scale) ===
        "total_assets": "资产总额",
        "total_liabilities": "负债总额",
        "common_equity_begin": "期初股东权益",
        "common_equity_end": "期末股东权益",
        "total_debt": "有息负债 (总借款)",
        "short_term_debt": "短期借款",
        "long_term_debt": "长期借款",
        "cash_and_equivalents": "现金及现金等价物",
        
        # === 2. 利润表 (Income Statement) ===
        "revenue": "营业收入",
        "revenue_ttm": "营业收入 (TTM)",
        "gross_profit": "毛利",
        "operating_profit": "营业利润",
        "net_profit": "净利润",
        "net_profit_ttm": "净利润 (TTM)",
        "net_interest_income": "利息净收入",
        "net_fee_income": "手续费及佣金净收入",
        "provision_expense": "资产/信用减值损失",
        
        # === 3. 资产质量 (Asset Quality - Bank) ===
        "total_loans": "贷款总额",
        "loan_loss_allowance": "贷款减值准备",
        "npl_balance": "不良贷款余额",
        "npl_ratio": "不良贷款率",
        "provision_coverage": "拨备覆盖率",
        "core_tier1_ratio": "核心一级资本充足率",
        "special_mention_ratio": "关注类贷款占比",
        
        # === 4. 股票数据与回购 (Per Share & Payout) ===
        "eps": "每股收益 (EPS)",
        "eps_ttm": "每股收益 (TTM)",
        "shares_outstanding": "期末总股本",
        "shares_diluted": "稀释后总股数",
        "dividend_per_share": "每股股利 (DPS)",
        "dividend_amount": "分红总额",
        "dividend_yield": "股息率",
        "buyback_amount": "回购总额",
        "buyback_ratio": "回购率",
        
        # === 5. 现金流与债务 (Cash Flow & Ratios) ===
        "operating_cashflow": "经营活动现金流",
        "free_cashflow_ttm": "自由现金流 (TTM)",
        "debt_to_equity": "产权比率 (D/E)",
        "interest_coverage": "利息保障倍数",
        "current_ratio": "流动比率",
        
        # === 辅助字段 (Auxiliary Fields) ===
        "treasury_shares": "库存股数量",
        "report_date": "会计周期",
        "report_type": "报告类型",
        "currency": "货币"
    }
    
    reverse_names = {v: k for k, v in friendly_names.items()}

    def format_val(k, v, report_type="unknown"):
        # Special handling for report_date (会计周期)
        if k == "report_date" and isinstance(v, str):
            try:
                # Parse date like "2022-03-31"
                parts = v.split('-')
                if len(parts) == 3:
                    year, month, day = parts
                    month_day = f"{month}-{day}"
                    
                    # Dynamic mapping based on report_type
                    if month_day == "12-31":
                        if report_type == "annual": return f"{year}年1月-12月 (全年)"
                        if report_type == "quarterly": return f"{year}年10月-12月 (Q4)"
                        return f"{year}-12-31" # Neutral if unknown
                    
                    elif month_day == "06-30":
                        if report_type == "interim": return f"{year}年1月-6月 (中期)"
                        if report_type == "quarterly": return f"{year}年4月-6月 (Q2)"
                        return f"{year}-06-30"

                    # Standard quarters
                    quarter_map = {
                        "03-31": f"{year}年1月-3月 (Q1)",
                        "09-30": f"{year}年7月-9月 (Q3)"
                    }
                    return quarter_map.get(month_day, v)
            except:
                pass
        
        if not isinstance(v, (int, float)): return str(v)
        
        # 1. Ratio fields - direct display with %
        ratios = ["ratio", "yield", "roe", "margin", "coverage"]
        if any(x in k for x in ratios):
            return f"{v:.2f}%"
        
        # 2. Per-share metrics - high precision decimals
        if k in ["eps", "dividend_per_share", "dps", "dividend"]:
            return f"{v:.4f}"
        
        # 3. Share counts - integer or billions
        if "shares" in k or k == "shares_outstanding":
                if v > 100_000_000: return f"{v/100_000_000:.2f} 亿股"
                return f"{v:,.0f}"

        # 4. Large amounts - always in billions (亿)
        # includes: revenue, profit, income, expense, loans, assets, liabilities, capital, equity
        amount_keywords = ["revenue", "income", "expense", "profit", "loans", "assets", 
                            "liabilities", "capital", "equity", "allowance", "paid", "amount", "rwa"]
        if any(kw in k for kw in amount_keywords):
            return f"{v/100_000_000:.4f} 亿"
        
        # 5. Fallback - if value is large, assume it's an amount
        if v > 10_000:
            return f"{v/100_000_000:.4f} 亿"
        return f"{v:,.2f}"

    def parse_edited_val(k, v_str):
        v_str = str(v_str).strip().replace(',', '')
        try:
            if "亿" in v_str:
                return float(v_str.replace('亿', '').strip()) * 100_000_000
            if "%" in v_str:
                return float(v_str.replace('%', '').strip()) / 100.0
            return float(v_str)
        except:
            return v_str
    c1, c2, c3 = st.columns(3)
    
    with c1:
        import_type = st.radio("数据类型 (Type)", [
            "📈 行情 (Market)", 
            "📊 期权 (Options)",
            "📋 财务 (Financial)", 
            "📄 PDF/图片 (Document)"
        ], horizontal=False)
    
    with c2:
        if "PDF/图片" in import_type:
            import_mode = "incremental" # Document import is usually single point
            st.info("模式：智能提取与增量更新")
        else:
            import_mode = st.radio(
                "导入模式 (Mode)", 
                ["全覆盖 (Overwrite)", "增量 (Incremental)"],
                horizontal=False,
                help="全覆盖：更新重叠日期的数据 | 增量：仅补充缺失日期"
            )
        mode = "overwrite" if "全覆盖" in import_mode else "incremental"
    
    with c3:
        # Asset Filter
        from engine.universe_manager import get_universe_assets_v2
        all_assets = get_universe_assets_v2()
        asset_options = {a['asset_id']: f"{a['asset_id']} ({a['symbol_name']})" for a in all_assets}
        
        selected_assets = st.multiselect(
            "限制资产 (Limit Assets)" if "PDF/图片" not in import_type else "目标资产 (Target Asset)",
            options=list(asset_options.keys()),
            format_func=lambda x: asset_options.get(x, x),
            placeholder="默认所有" if "PDF/图片" not in import_type else "必须选择一个资产",
            max_selections=1 if "PDF/图片" in import_type else None
        )
        target_assets = selected_assets if selected_assets else None
    
    # 1. Filters Row
    f1, f2, f3 = st.columns(3)
    start_date, end_date = None, None
    
    with f1:
        if "PDF/图片" not in import_type:
            start_date = st.date_input("开始日期 (Start)", value=None, help="留空则从最早数据开始")
            
    with f2:
        if "PDF/图片" not in import_type:
            end_date = st.date_input("结束日期 (End)", value=None, help="留空则处理至最新数据")
            
    # f3 remains placeholder for alignment

    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("#### 📤 上传文件 (Upload)")
        
        # Smart extension selection: 
        # Financial reports can be CSV or PDF/Images. 
        if "行情" in import_type or "期权" in import_type:
            import_exts = ["csv"]
        else:
            import_exts = ["csv", "pdf", "png", "jpg", "jpeg"]
            
        st.caption(f"支持格式: {', '.join(import_exts).upper()}")
        uploaded_files = st.file_uploader("选择文件", type=import_exts, accept_multiple_files=True)
        
        
        if "财务" in import_type or ("Document" in import_type):
            is_yi = st.checkbox("数值单位为“亿”", value=True, help="如果勾选，系统会自动将数值乘以 10^8。注：仅对 CSV 或部分数值提取生效。")
        else:
            is_yi = False 
        
        if st.button("开始执行导入 (Run Import)", type="primary"):
            if uploaded_files:
                with st.spinner(f"正在处理 {len(uploaded_files)} 个文件..."):
                    from utils.csv_handler import parse_and_import_csv, parse_and_import_financials_csv
                    from utils.batch_image_processor import BatchImageProcessor
                    
                    all_results = []
                    for uploaded_file in uploaded_files:
                        fname = uploaded_file.name.lower()
                        is_document = fname.endswith(('.pdf', '.png', '.jpg', '.jpeg'))
                        
                        # 1. Logic for Unstructured Documents (PDF/Images)
                        if is_document:
                            if not target_assets:
                                st.error(f"❌ '{uploaded_file.name}': 请先在右侧选择一个「目标资产」。")
                                continue
                            proc = BatchImageProcessor()
                            # Perform recognition only (auto_save=False by default now)
                            res = proc.process_single_image(uploaded_file, target_assets[0], auto_save=False)
                            # Calc missing keys for batch summary
                            extracted = set(res.get("extracted_data", {}).keys())
                            # Expected keys excluding ignore list
                            std_ignore = {"report_date", "pe_ttm", "pb", "dividend", "shares_diluted", "treasury_shares", "dividend_yield", "roae", "roaa", "shares_outstanding"}
                            expected = {k: v for k, v in friendly_names.items() if k not in std_ignore}
                            missing = [v for k, v in expected.items() if k not in extracted]
                            
                            count = len(extracted)
                            if missing:
                                res["msg"] = f"提取 {count} 项 (缺: {' '.join(missing)})"
                            else:
                                res["msg"] = f"完美匹配 ({count} 项)"
                                
                            all_results.append(res)
                        
                        # 2. Logic for Structured Data (CSV)
                        elif "行情" in import_type:
                            success, msg = parse_and_import_csv(uploaded_file, None, None, mode=mode, start_date=start_date, end_date=end_date, target_assets=target_assets)
                            all_results.append({"status": "success" if success else "error", "file_name": uploaded_file.name, "msg": msg, "success": success})
                        
                        # 3. Logic for Options CSV
                        elif "期权" in import_type:
                            try:
                                # Save uploaded file temporarily
                                import tempfile
                                import os
                                with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp_file:
                                    tmp_file.write(uploaded_file.getvalue())
                                    tmp_path = tmp_file.name
                                
                                # Import options data
                                from scripts.import_options_data import import_options_from_csv
                                result = import_options_from_csv(tmp_path)
                                
                                # Clean up
                                os.unlink(tmp_path)
                                
                                # Format success message
                                assets_count = len(result.get("assets_covered", []))
                                success_count = result.get("success_count", 0)
                                failed_assets = result.get("failed_assets", [])
                                
                                # Market breakdown
                                mkt_counts = result.get("market_counts", {})
                                breakdown_strs = []
                                for mkt, data in mkt_counts.items():
                                    if isinstance(data, dict):
                                        breakdown_strs.append(f"{mkt}: {data.get('asset_count', '?')} 个资产 ({data.get('rows', '?')} 条合约)")
                                    else:
                                        breakdown_strs.append(f"{mkt}: {data} 条合约")
                                
                                breakdown_msg = "，其中 " + "，".join(breakdown_strs) if breakdown_strs else ""
                                
                                msg = f"导入 {success_count} 条记录 (覆盖 {assets_count} 个资产){breakdown_msg}"
                                if failed_assets:
                                    f_list = ', '.join(failed_assets[:5])
                                    suffix = f"...等 {len(failed_assets)} 个" if len(failed_assets) > 5 else ""
                                    msg += f"。⚠️ 未匹配: {f_list}{suffix}"
                                
                                all_results.append({
                                    "status": "success", 
                                    "file_name": uploaded_file.name, 
                                    "msg": msg, 
                                    "success": True,
                                    "details": result # Store detailed result if needed later
                                })
                            except Exception as e:
                                all_results.append({
                                    "status": "error", 
                                    "file_name": uploaded_file.name, 
                                    "msg": f"期权导入失败: {str(e)}", 
                                    "success": False
                                })
                        
                        else:
                            # Financial CSV
                            scale = 100_000_000 if is_yi else 1
                            success, msg = parse_and_import_financials_csv(uploaded_file, unit_scale=scale, mode=mode, start_date=start_date, end_date=end_date, target_assets=target_assets)
                            all_results.append({"status": "success" if success else "error", "file_name": uploaded_file.name, "msg": msg, "success": success})
                    
                    # Aggregate Report
                    if len(all_results) == 1:
                        final_res = all_results[0]
                        if "success" not in final_res:
                            final_res["success"] = (final_res.get("status") == "success")
                        st.session_state['import_result'] = final_res
                    else:
                        success_count = sum(1 for r in all_results if r.get('status') == 'success' or r.get('success'))
                        summary_msg = f"已完成 {len(all_results)} 个文件的处理。成功: {success_count}, 失败: {len(all_results)-success_count}"
                        st.session_state['import_result'] = {
                            "success": True, 
                            "msg": summary_msg, 
                            "details": all_results
                        }
            else:
                st.warning("请先上传文件")

    with col2:
        if "行情" in import_type:
            st.info("""
            **行情 CSV 格式规范：**
            - `date`: YYYY-MM-DD
            - `symbol`: 代码 (如 00001.HK)
            - `close`: 收盘价
            - `volume`: 成交量 (可选)
            """)
        elif "期权" in import_type:
            st.info("""
            **期权 CSV 格式规范：**
            - `underlying_symbol`: 标的代码
            - `Type`: 期权类型 (C/P)
            - `Strike`: 行权价
            - `ExpiryDate`: 到期日 (YYYY-MM-DD)
            - `Market_Price`: 市场价
            - `IV`, `Delta`, `Gamma`, `Theta` (可选)
            """)
        elif "PDF/图片" in import_type:
            st.info("""
            **📄 智能识别说明：**
            - **支持格式**: PDF 报表, 终端截图 (PNG/JPG)。
            - **核心识别**: 营收、净利润、EPS、分红。
            - **银行专修**: 核心一级资本、利息收入、不良率、拨备等。
            - **逻辑**: 系统将通过正则与文本分析自动提取数值。
            """)
        else:
            st.info("""
            **财报 CSV 格式规范：**
            - `symbol`: 代码 (如 00001.HK)
            - `as_of_date`: 截止日期 (YYYY-MM-DD)
            - `revenue_ttm`: 营收 (TTM)
            - `net_income_ttm`: 净利润 (TTM)
            - `currency`: 货币 (可选，默认 CNY)
            - 支持其他资产负债表列名 (total_assets, debt_to_equity 等)。
            """)

    if 'import_result' in st.session_state:
        st.markdown("---")
        st.markdown("#### 📊 导入报告 (Import Report)")
        res = st.session_state['import_result']

        res = st.session_state['import_result']


        # 3. Status Message & Save Feedback
        if res.get("status") == "saved":
            feedback = res.get("save_feedback", "数据已提交至数据库。")
            if "失败" in feedback and "失败 0" not in feedback:
                st.warning(f"⚠️ **保存完成，但存在异常**：\n\n{feedback}")
            else:
                st.success(f"✅ **{feedback}**")
            if st.button("🔄 开始新的导入"):
                del st.session_state['import_result']
                st.rerun()
                
        elif res.get("success"):
            # A) Batch Result
            if "details" in res:
                st.success(f"✅ **{res.get('msg')}**")
                # Batch details are shown in the table below
            
            # B) Single File Result
            else:
                # CRITICAL FIX: Market Data (CSV) does not return 'extracted_data' with financial metrics.
                # We must differentiate logic based on import_type.
                if "行情" in import_type:
                     st.success(f"✅ **{res.get('msg', '导入成功')}**")
                elif "extracted_data" not in res:
                     # A. Financial CSV (no OCR extraction)
                     st.success(f"**{res.get('msg', '导入成功')}**")
                else:
                    # B. OCR Documents: Check for missing indicators
                    extracted_keys = set(res.get("extracted_data", {}).keys())
                    
                    # Filter out auxiliary and legacy fields from expectations
                    ignore_keys = {
                        "shares_diluted", "treasury_shares", "report_date",
                        "dividend", "pe_ttm", "pb",
                        "dividend_yield", "roae", "roaa"
                    }
                    
                    expected_keys = {k: v for k, v in friendly_names.items() if k not in ignore_keys}
                    missing_items = [v for k, v in expected_keys.items() if k not in extracted_keys]
                    
                    count_info = f"共提取 {len(extracted_keys)} 个指标"
                    
                    if missing_items:
                        st.success(f"✅ **识别完成**：{count_info}。 (⚠️ 未找到：{'、'.join(missing_items)})")
                    else:
                        st.success(f"✅ **识别完成**：{count_info} (完美匹配)")

                    with st.expander("🛠️ 调试信息 (若提取结果为空，请检查此处)", expanded=(len(extracted_keys) == 0)):
                        # Show debug logs first (most important for diagnosis)
                        if "debug" in res and res["debug"]:
                            st.markdown("**📋 解析日志**:")
                            st.code("\n".join(res["debug"]), language=None)
                            st.markdown("---")
                        
                        # Then show raw text
                        raw_txt = res.get("raw_text", "")
                        st.write(f"**提取文本长度**: {len(raw_txt)} 字符")
                        if len(raw_txt) < 100:
                            st.warning("⚠️ 文本极短，可能是图片扫描件或加密文档。")
                        st.write("**文本片段 (前2000字符)**:")
                        st.text(raw_txt[:2000])
                
        else:
            st.error(res.get("msg", "识别失败"))
            if "error" in res:
                st.markdown("**错误详情 (可点击右侧复制):**")
                st.code(res['error'], language=None)
            
        # 4. Editable Data Detail (Single File)
        final_metrics_to_save = {}
        if "extracted_data" in res and res["extracted_data"]:
            st.markdown("##### 📝 已提取数据明细 (可直接双击数值进行修正)")
            data_rows = []
            for k, v in res["extracted_data"].items():
                if k not in friendly_names: continue # Skip internal or metadata fields
                if k == "dividend": continue # Skip legacy duplicate
                data_rows.append({"指标项": friendly_names.get(k, k), "数值": format_val(k, v, res.get("report_type", "unknown"))})
            
            edited_df = st.data_editor(
                pd.DataFrame(data_rows), 
                use_container_width=True, 
                key="single_import_editor",
                hide_index=True,
                height=600  # Increased height to show more rows
            )
            # Reconstruct dict from edited dataframe
            for _, row in edited_df.iterrows():
                key = reverse_names.get(row["指标项"], row["指标项"])
                final_metrics_to_save[key] = parse_edited_val(key, row["数值"])

        # 5. Saving Logic 
        pending_docs_info = []
        if "details" in res and isinstance(res["details"], list):
            pending_docs_info = [d for d in res["details"] if isinstance(d, dict) and d.get("status") == "success" and "extracted_data" in d]
        elif res.get("status") == "success" and final_metrics_to_save:
            pending_docs_info = [{"asset_id": res["asset_id"], "report_date": res["report_date"], "file_name": res["file_name"], "extracted_data": final_metrics_to_save}]
            
            

        # 6. Debug & Multi-file Details
        if "debug" in res and res["debug"] and "details" not in res:
            with st.expander("🛠️ 解析调试日志 (Parser Breakpoints)"):
                st.code("\n".join(res["debug"]), language=None)
            
        if "raw_text" in res and res["raw_text"]:
            with st.expander("📄 提取原始文本 (Raw Extracted Text)"):
                st.code(res["raw_text"], language=None)
            
        if "details" in res and isinstance(res["details"], list):
            # 1. Show summary table (PDF/Batch Logic)
            st.markdown("#### 📊 多文件处理汇总")
            details_df = pd.DataFrame(res["details"])
            display_cols = {"file_name": "文件名", "status": "状态", "report_date": "日期", "metrics_count": "项数", "msg": "详情"}
            actual_cols = [c for c in display_cols.keys() if c in details_df.columns]
            st.table(details_df[actual_cols].rename(columns=display_cols))
            
        elif "details" in res and isinstance(res["details"], dict):
            # 2. Show stats summary (Options Logic)
            stats = res["details"]
            
            c1, c2 = st.columns(2)
            with c1:
                if stats.get("failed_assets"):
                    st.markdown("#### ⚠️ 未匹配资产")
                    st.dataframe(pd.DataFrame(stats["failed_assets"], columns=["Underlying Asset Symbol"]), hide_index=True)
                else:
                    st.info("所有资产均成功匹配")
            
            with c2:
                if stats.get("details"):
                    st.markdown("#### ❌ 错误日志 (前10条)")
                    st.text("\n".join(stats["details"]))
                else:
                    st.info("无错误日志")
            
            # 2. File selector for detailed editing and debugging
            # Include ALL files (even those with empty extracted_data) to show debug logs
            all_files = res["details"]
            if isinstance(all_files, list) and all_files:
                st.markdown("---")
                st.markdown("#### 📝 数值校验与修正")
                
                # Create file selector
                file_names = [d["file_name"] for d in all_files]
                if len(file_names) > 1:
                    selected_file = st.selectbox(
                        "选择文件进行编辑",
                        file_names,
                        key="file_selector"
                    )
                    selected_idx = file_names.index(selected_file)
                else:
                    selected_idx = 0
                
                d = all_files[selected_idx]
                
                # Show file status
                status_emoji = "✅" if d.get('status') == 'saved' else "⏳"
                st.info(f"{status_emoji} **当前文件**: {d['file_name']} | **报告日期**: {d.get('report_date', 'N/A')} | **状态**: {d.get('status', 'pending')}")
                
                # Check if we have extracted data
                has_data = "extracted_data" in d and d["extracted_data"]
                
                if has_data:
                    # Build editable table
                    d_rows = []
                    for k, v in d["extracted_data"].items():
                        if k not in friendly_names: continue # Skip internal/metadata
                        if k == "dividend": continue # Skip legacy duplicate
                        d_rows.append({"指标项": friendly_names.get(k, k), "数值": format_val(k, v, d.get("report_type", "unknown"))})
                    
                    # Show data editor
                    st.markdown("##### 可编辑数据表 (双击单元格修改)")
                    m_edited_df = st.data_editor(
                        pd.DataFrame(d_rows), 
                        key=f"multi_editor_{selected_idx}",
                        hide_index=True,
                        use_container_width=True,
                        height=min(800, len(d_rows) * 35 + 50)
                    )
                    
                    # Update the source dict so the 'Save' button picks it up
                    new_metrics = {}
                    for _, row in m_edited_df.iterrows():
                        k = reverse_names.get(row["指标项"], row["指标项"])
                        new_metrics[k] = parse_edited_val(k, row["数值"])
                    d["extracted_data"] = new_metrics
                else:
                    # No data extracted - show warning
                    st.warning(f"⚠️ **该文件未提取到任何数据** ({d.get('msg', '未知原因')})")
                    st.markdown("**请查看下方的调试日志以诊断问题**")
                
                # Always show raw text and debug logs (especially important when extraction fails)
                col_debug1, col_debug2 = st.columns(2)
                with col_debug1:
                    if "raw_text" in d and d["raw_text"]:
                        with st.expander(f"📄 查看原始文本 ({len(d['raw_text'])} 字符)", expanded=not has_data):
                            st.code(d["raw_text"][:5000], language=None)  # Limit to first 5000 chars for performance
                            if len(d["raw_text"]) > 5000:
                                st.caption(f"(仅显示前5000字符，总长度: {len(d['raw_text'])})")
                
                with col_debug2:
                    if "debug" in d and d["debug"]:
                        with st.expander(f"🛠️ 查看解析日志 ({len(d['debug'])} 条)", expanded=not has_data):
                            st.code("\n".join(d["debug"]), language=None)

        # Bottom action buttons
        if pending_docs_info:
            st.warning("⚠️ **数据待确认**：请检查并修正上方表格内的数值。确认无误后点击下方按钮存入数据库。")
        
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if pending_docs_info and st.button("💾 确认所有修正并保存至数据库", type="primary", use_container_width=True):
                with st.spinner("正在写入数据库并存证..."):
                    from utils.batch_image_processor import BatchImageProcessor
                    proc = BatchImageProcessor()
                    saved_count = 0
                    skip_count = 0
                    err_count = 0
                    details_msg = []
                    
                    for doc in pending_docs_info:
                        source_info = f"DOCUMENT_OCR ({doc['file_name']})"
                        db_res = proc.save_metrics_to_db(doc['asset_id'], doc['report_date'], doc['extracted_data'], source_info)
                        
                        if db_res.get("status") == "success":
                            saved_count += 1
                        elif db_res.get("status") == "skipped":
                            skip_count += 1
                            details_msg.append(f"• {doc['file_name']}: {db_res.get('msg')}")
                        elif db_res.get("status") == "error":
                            err_count += 1
                            details_msg.append(f"❌ {doc['file_name']}: {db_res.get('msg')}")
                            
                    st.session_state['import_result']["status"] = "saved"
                    feedback = f"处理结束: 成功 {saved_count}, 跳过 {skip_count}, 失败 {err_count}。"
                    if details_msg:
                        feedback += "\n" + "\n".join(details_msg)
                    st.session_state['import_result']["save_feedback"] = feedback
                    st.rerun()
        
        with col_btn2:
            if st.button("🗑️ 清除报告记录", use_container_width=True):
                del st.session_state['import_result']
                st.rerun()


def reconstruct_dashboard_data_from_snapshot(details):
    """
    Reconstruct DashboardData object from snapshot dictionary.
    Maps database tables (snapshot, metrics, risk_card, etc.) back to the 
    structure expected by render_page().
    """
    from analysis.dashboard import DashboardData
    
    if not details or details['snapshot'].empty:
        return None
        
    s = details['snapshot'].iloc[0]
    
    # 1. Base Info
    symbol = s['asset_id']
    symbol_name = s['symbol_name']
    
    # 2. Risk Card (Convert single row DF to dict)
    risk_card = {}
    if not details['risk_card'].empty:
        risk_card = details['risk_card'].iloc[0].to_dict()
        
    # 3. Metrics (Convert key-value rows to dict)
    metrics = {}
    if not details['metrics'].empty:
        metrics = dict(zip(details['metrics']['metric_key'], details['metrics']['value']))
    
    # 4. Quality (Convert single row DF to dict)
    quality = {}
    if not details['quality'].empty:
        quality = details['quality'].iloc[0].to_dict()
        
    # 5. Behavior Flags
    behavior_flags = []
    if not details['behavior'].empty:
        behavior_flags = details['behavior'].to_dict(orient='records')
        
    # 6. Overlay (Reconstruct nested dict structure)
    # The database stores overlay flat or partially normalized. 
    # We need to map it back to {individual: {}, sector: {}, market: {}}
    overlay = {
        'individual': {},
        'sector': {},
        'market': {},
        'asset_type': s.get('category') or s.get('asset_type'), # 'category' alias used in SQL fix
        'index_role': s.get('index_role')
    }
    
    if not details['overlay'].empty:
        ov_row = details['overlay'].iloc[0]
        # Mapping logic based on column prefixes in risk_overlay_snapshot table
        # Assuming column names like: ind_*, sector_*, market_*
        for col, val in ov_row.items():
            if col.startswith('ind_'):
                overlay['individual'][col] = val
            elif col.startswith('sector_'):
                overlay['sector'][col] = val
                overlay['market'][col] = val
            # Map specific core fields if names match exactly or close
            if col == 'stock_vs_sector_rs_3m': overlay['sector'][col] = val
        
        # 6b. Explicit Mapping & Name Resolution for History
        def _backfill_recent_cycle(layer_node, as_of_date, default_vol=None):
            if layer_node.get('recent_cycle') or not layer_node.get('id'):
                return
            try:
                asset_id = layer_node['id']
                conn = get_connection()
                query = f"""
                    SELECT * FROM (
                        SELECT trade_date, close 
                        FROM vera_price_cache 
                        WHERE symbol = ? AND trade_date <= ?
                        ORDER BY trade_date DESC LIMIT 400
                    ) ORDER BY trade_date ASC
                """
                df_prices = pd.read_sql_query(query, conn, params=(asset_id, as_of_date), parse_dates=['trade_date'])
                conn.close()
                
                if not df_prices.empty:
                    df_prices.set_index('trade_date', inplace=True)
                    price_series = df_prices['close']
                    vol_1y = default_vol
                    if not vol_1y:
                        rets = price_series.pct_change().dropna()
                        vol_1y = rets.std() * (252 ** 0.5)
                    
                    recent_engine = RecentCycleEngine()
                    recent_info = recent_engine.evaluate(price_series, vol_1y if vol_1y else 0.0)
                    layer_node['recent_cycle'] = {
                        "state": recent_info.state,
                        "label": recent_info.state_label_zh,
                        "off_high_1y": float(recent_info.off_high_1y),
                        "dd_days": int(recent_info.dd_days),
                        "dd_sigma": float(recent_info.dd_sigma),
                        "peak_price": float(recent_info.peak_1y),
                        "peak_date": recent_info.peak_date.strftime("%Y-%m-%d") if pd.notnull(recent_info.peak_date) else None
                    }
            except Exception as e:
                print(f"Failed to backfill recent cycle for {layer_node.get('id')}: {e}")

        # Individual
        if not overlay['individual'].get('state'): overlay['individual']['state'] = ov_row.get('ind_dd_state')
        if not overlay['individual'].get('path_risk'): overlay['individual']['path_risk'] = ov_row.get('ind_path_risk')
        if not overlay['individual'].get('vol_regime'): overlay['individual']['vol_regime'] = ov_row.get('ind_vol_regime')
        if not overlay['individual'].get('position_pct'): overlay['individual']['position_pct'] = ov_row.get('ind_position_pct')
        overlay['individual']['volatility_1y'] = ov_row.get('ind_volatility_1y')
        
        # Drawdown JSON
        import json
        if 'ind_drawdown' in ov_row and ov_row['ind_drawdown']:
            try: overlay['individual']['drawdown'] = json.loads(ov_row['ind_drawdown'])
            except: pass

        # Backfill Recent Cycle Info if missing (for legacy snapshots)
        _backfill_recent_cycle(overlay['individual'], s['as_of_date'], metrics.get('annual_volatility'))

        # Sector
        s_id = ov_row.get('sector_etf_id')
        overlay['sector']['id'] = s_id
        overlay['sector']['state'] = ov_row.get('sector_dd_state')
        overlay['sector']['path_risk'] = ov_row.get('sector_path_risk')
        overlay['sector']['stock_vs_sector_rs_3m'] = ov_row.get('stock_vs_sector_rs_3m')
        overlay['sector']['alignment'] = ov_row.get('sector_alignment')
        overlay['sector']['volatility_1y'] = ov_row.get('sector_volatility_1y')
        if 'sector_drawdown' in ov_row and ov_row['sector_drawdown']:
            try: overlay['sector']['drawdown'] = json.loads(ov_row['sector_drawdown'])
            except: pass
        if s_id and not overlay['sector'].get('name'):
            overlay['sector']['name'] = get_asset_name(s_id)
        # Recent Cycle Mapping
        if 'sector_recent_cycle' in ov_row:
            overlay['sector']['recent_cycle'] = ov_row.get('sector_recent_cycle')
        else:
            _backfill_recent_cycle(overlay['sector'], s['as_of_date'])

        # Market
        m_id = ov_row.get('market_index_id')
        overlay['market']['id'] = m_id
        overlay['market']['state'] = ov_row.get('market_dd_state')
        overlay['market']['path_risk'] = ov_row.get('market_path_risk') # Ensure path risk is mapped
        overlay['market']['market_regime_label'] = ov_row.get('market_regime_label')
        overlay['market']['volatility_1y'] = ov_row.get('market_volatility_1y')
        if 'market_drawdown' in ov_row and ov_row['market_drawdown']:
            try: overlay['market']['drawdown'] = json.loads(ov_row['market_drawdown'])
            except: pass
        if m_id and not overlay['market'].get('name'):
            overlay['market']['name'] = get_asset_name(m_id)
        # Recent Cycle Mapping
        if 'market_recent_cycle' in ov_row:
            overlay['market']['recent_cycle'] = ov_row.get('market_recent_cycle')
        else:
            _backfill_recent_cycle(overlay['market'], s['as_of_date'])
            
    # 7. Value (Reconstruct from metrics/snapshot)
    # The 'value' dict in DashboardData usually comes from ValuationAnalyzer
    # We try to rebuild it from what we have
    val_status = s.get('valuation_status', 'UNKNOWN')
    val_key = "UNKNOWN"
    if val_status in ["Undervalued / Deep", "Deeply Undervalued"]: val_key = "DEEP_UNDERVALUE"
    elif val_status in ["Fair-Low", "Undervalued"]: val_key = "FAIR_LOW"
    elif val_status in ["Fairly Valued", "Fair"]: val_key = "FAIR"
    elif val_status == "Overvalued": val_key = "OVERVALUE"
    elif val_status == "Extremely Overvalued": val_key = "EXTREME_OVERVALUE"
    
    value = {
        'current_pe': metrics.get('pe_ttm'),
        'current_pe_static': metrics.get('pe_static'),
        'current_pb': metrics.get('pb_ratio'),
        'valuation_status': val_status,
        'valuation_status_key': val_key,
        'pe_percentile': risk_card.get('pe_percentile') # risk_card often holds PE pct too? Check schema
    }
    # If valuation status details were stored in metrics or specific table, map them here.
    # For now, simplistic mapping.
    
    # 8. Path (Reconstruct from risk_card)
    path = {
        'has_new_high': False # Default, unless stored
    }
    # Try to infer new high from recovery_progress
    if risk_card.get('recovery_progress', 0) >= 1.0:
        path['has_new_high'] = True
        
    # 9. Market Environment
    # Often stored in overlay in flat structure or separate text
    market_env = {
        'regime_label': overlay['market'].get('market_regime_label')
    }

    # 10. Overall Conclusion
    # Often stored in decision_log or constructed. 
    # Snapshot table has 'logic_rationale' or similar? 
    # Check `decision` table in details
    conclusion = "无综合裁定记录"
    if 'decision' in details and not details['decision'].empty:
        # decision_log might have 'action_signal', 'rationale'
        d_row = details['decision'].iloc[0]
        conclusion = d_row.get('rationale', "无详细记录")

    current_price = 0.0
    # Prioritize metrics, then fallback to snapshot table
    if 'current_price' in metrics:
        try: current_price = float(metrics['current_price'])
        except: pass
    elif 'current_price' in s and pd.notna(s['current_price']):
        try: current_price = float(s['current_price'])
        except: pass

    data = DashboardData(
        symbol=symbol,
        symbol_name=symbol_name,
        price=current_price,
        change_percent=None, # Snapshot may not have daily change recorded
        report_date=s['as_of_date'],
        overall_conclusion=conclusion,
        path=path,
        position={}, # risk_card has position_zone, stored in overlay['individual']
        market_environment=market_env,
        value=value,
        overlay=overlay,
        behavior_suggestion=s.get('action_signal', ''), # Snapshot might store signal in basic info? Or decision table.
        cognitive_warning=s.get('risk_level', ''), # Using risk_level as proxy if warning not text
        
        quality=quality,
        behavior_flags=behavior_flags,
        risk_card=risk_card,
        valuation_path=None, # Might not be fully stored in snapshot yet
        expert_audit=None
    )
    
    # 11. Attempt to Reconstruct Expert Audit (NEW)
    try:
        from vera.explain.expert_audit_builder import ExpertAuditBuilder
        eval_res = {
            "d_state": risk_card.get("state") or risk_card.get("d_state"),
            "d_label_zh": risk_card.get("desc"),
            "i_state": overlay["market"].get("index_risk_state", "UNKNOWN"),
            "confidence": 0.85
        }
        # Invert from overlay/metrics
        indicators = {
            "vol_pctile": 0.5, # Fallback
            "recovery_progress": risk_card.get("recovery_progress", 0.0),
            "ind_position_pct": overlay["individual"].get("ind_position_pct", 0.5)
        }
        # Re-fetch history for the snapshot date
        formatted_history = []
        conn = get_connection()
        rows = conn.execute("""
            SELECT trade_date, state, confirmed 
            FROM drawdown_state_history 
            WHERE asset_id = ? AND trade_date <= ?
            ORDER BY trade_date DESC LIMIT 10
        """, (symbol, s['as_of_date'])).fetchall()
        conn.close()
        for r in reversed(rows):
            formatted_history.append({"t": r[0], "d_state": r[1], "confirmed": bool(r[2])})
            
        data.expert_audit = ExpertAuditBuilder.build(eval_res, indicators, formatted_history)
    except Exception as e:
        print(f"Historical Audit Rebuild Warning: {e}")
    
    # Refine specific text fields if available in other tables
    if 'decision' in details and not details['decision'].empty:
        d_row = details['decision'].iloc[0]
        if 'behavior_suggestion' in d_row: data.behavior_suggestion = d_row['behavior_suggestion']
        if 'cognitive_warning' in d_row: data.cognitive_warning = d_row['cognitive_warning']
        
    return data

def render_snapshot_detail(snapshot_id: str):
    """渲染快照详情页面 - 使用 Analysis 统一布局"""
    details = get_snapshot_details(snapshot_id)
    
    if details is None or details['snapshot'].empty:
        st.error("未找到快照信息")
        if st.button("🔙 返回列表"):
            if 'view_snapshot_id' in st.session_state:
                del st.session_state['view_snapshot_id']
            st.rerun()
        return
    
    # 1. 顶部导航与印戳
    st.markdown("""
        <style>
        .snapshot-banner {
            background-color: #7c2d12;
            color: #ffedd5;
            padding: 10px 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border: 1px solid #fb923c;
        }
        .snapshot-tag {
            font-weight: bold;
            font-size: 1.1em;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        </style>
        <div class="snapshot-banner">
            <div class="snapshot-tag">
                <span>📸 历史快照模式 (Snapshot View)</span>
                <span style="font-size:0.8em; opacity:0.8; font-weight:normal;"> | ID: """ + snapshot_id[:8] + """...</span>
            </div>
            <div style="font-size: 0.9em;">
                不可交互 · 仅供留档参考
            </div>
        </div>
    """, unsafe_allow_html=True)

    col_back, _ = st.columns([1, 5])
    with col_back:
        if st.button("🔙 退出快照 (Exit)", use_container_width=True):
            if 'view_snapshot_id' in st.session_state:
                del st.session_state['view_snapshot_id']
            if "view_snapshot_id" in st.query_params:
                st.query_params.pop("view_snapshot_id")
            st.rerun()

    # 2. 数据重构
    try:
        dash_data = reconstruct_dashboard_data_from_snapshot(details)
        if not dash_data:
            st.error("数据重构失败")
            return
            
        # 3. 复用主渲染逻辑
        # Pass report_date for chart filtering if needed
        render_page(dash_data, profile=None, chart_end_date=dash_data.report_date)
        
    except Exception as e:
        st.error(f"渲染快照时发生错误: {str(e)}")
        st.exception(e)

def render_history_dashboard(asset_id: str = None):
    """📊 Main Page Evaluation History / 主页面评估历史"""
    # 检查URL参数是否需要显示详情页面
    # 优先级: URL参数 > Session State
    qp_snapshot_id = st.query_params.get("view_snapshot_id", None)
    if qp_snapshot_id:
        st.session_state['view_snapshot_id'] = qp_snapshot_id
    
    # 检查是否需要显示详情页面
    if 'view_snapshot_id' in st.session_state:
        render_snapshot_detail(st.session_state['view_snapshot_id'])
        return
    
    # 检查URL参数是否指定了资产 (for persistency)
    display_code = None  # 用于显示的简化代码
    if not asset_id:
        asset_id = st.query_params.get("code")
        display_code = asset_id  # 保存原始代码用于显示
    else:
        display_code = asset_id
    

    if asset_id:
        # 如果 display_code 是完整的 Canonical ID，简化它用于显示
        if display_code and ':' in display_code:
            display_code = display_code.split(':')[-1]
        
        st.markdown(f"# 📊 {display_code} 评估历史")
        st.markdown(f"### Historical Assessments for {display_code}")
        if st.button("🌐 显示全部资产记录 (Show All Assets)"):
            # 清除 URL 参数中的 code
            if "code" in st.query_params:
                st.query_params.pop("code")
            st.session_state.history_filter = None
            st.rerun()
        

        history_df = get_asset_evaluation_history(asset_id)
    else:
        st.markdown("# 📊 评估历史记录")
        st.markdown("### Evaluation History Dashboard")
        # UI Element Removed as per user request
        show_all = st.session_state.get('history_show_all', False)
        history_df = get_evaluation_history(show_all=show_all)

    # Removed st.info and st.markdown("---")
    
    if not history_df.empty:
        # Standardize for display
        def simplify_symbol(s):
            if ':' in s: return s.split(':')[-1]
            if '.' in s: return s.split('.')[0]
            return s
            
        status_map = {
            "Undervalued / Deep": "🟩🟩 低估/深度 (Deeply Undervalued)",
            "Fair-Low": "🟩 合理偏低 (Fair-Low)",
            "Fairly Valued": "⬜ 合理 (Fairly Valued)",
            "Fair": "⬜ 合理 (Fair)",
            "Overvalued": "🟧 高估 (Overvalued)",
            "Extremely Overvalued": "🟥 严重高估 (Extremely Overvalued)",
            # Compatibility for legacy records
            "Deeply Undervalued": "🟩🟩 深度低估 (Deeply Undervalued)",
            "Undervalued": "🟩 低估 (Undervalued)"
        }
        
        display_df = history_df.copy()
        # Sort by creation time descending / 按创建时间降序排列
        display_df = display_df.sort_values('created_at', ascending=False).reset_index(drop=True)
        
        # 构造跳转链接URL
        # 格式: /?page=history&view_snapshot_id=ID&code=CODE
        display_df['link_code'] = display_df.apply(
            lambda x: f"/?page=history&view_snapshot_id={x['snapshot_id']}&code={simplify_symbol(x['asset_id'])}", 
            axis=1
        )
        display_df['symbol_name_show'] = display_df['symbol_name']
        
        display_df['状态'] = display_df['valuation_status'].map(status_map).fillna(display_df['valuation_status'])
        display_df['行情数据日期'] = pd.to_datetime(display_df['as_of_date']).dt.strftime('%Y-%m-%d')
        display_df['评估日期'] = pd.to_datetime(display_df['created_at']).dt.strftime('%Y-%m-%d')
        display_df['评估时间'] = pd.to_datetime(display_df['created_at']).dt.strftime('%H:%M:%S')
        
        # Action Bar
        ctrl_col1, ctrl_col2, ctrl_col3 = st.columns([3, 3, 4])
        with ctrl_col1:
            delete_placeholder = st.empty()
        with ctrl_col2:
            with st.popover("⚙️ 批量维护 (Maintenance)"):
                st.markdown("### 👁️ 显示设置 (View Settings)")
                current_show_all = st.session_state.get('history_show_all', False)
                show_all_check = st.checkbox("显示所有历史快照 / Show All Snapshots", value=current_show_all, help="勾选显示所有历史记录，不勾选仅显示最新一条")
                
                if show_all_check != current_show_all:
                    st.session_state.history_show_all = show_all_check
                    st.rerun()
                    
                st.markdown("---")
                st.markdown("### ⚠️ 危险操作 (Danger Zone)")
                
                if st.session_state.get("show_clear_all_confirm"):
                    st.error("⚠️ 确定要清空所有记录吗？此操作无法恢复！")
                    c1, c2 = st.columns(2)
                    if c1.button("✅ 确认 (Confirm)", type="primary", key="cfm_h_new"):
                        ok, msg = delete_all_evaluation_history()
                        if ok:
                            st.success(msg)
                            st.session_state.show_clear_all_confirm = False
                            if "history_mgmt_editor_fixed" in st.session_state:
                                del st.session_state["history_mgmt_editor_fixed"]
                            st.rerun()
                        else:
                            st.error(f"❌ 清空失败: {msg}")
                    if c2.button("❌ 取消 (Cancel)", key="cnl_h_new"):
                        st.session_state.show_clear_all_confirm = False
                        st.rerun()
                else:
                    if st.button("🗑️ 清空所有历史 (Clear All)", type="primary", use_container_width=True):
                        st.session_state.show_clear_all_confirm = True
                        st.rerun()

        st.info("💡 点击蓝色代码查看详情。勾选左侧方框进行批量删除。 / Click blue code to view details. Check box to delete.")

        # Prepare for Data Editor
        display_df.insert(0, "选择 (Select)", False)
        
        # Note: We display 'link_code' column but configure it to show code text using regex
        edit_cols = ["选择 (Select)", "link_code", "symbol_name_show", "状态", "行情数据日期", "评估日期", "评估时间", "snapshot_id"]
        
        edited_df = st.data_editor(
            display_df[edit_cols],
            column_config={
                "选择 (Select)": st.column_config.CheckboxColumn("删除", help="勾选以删除", default=False, width="small"),
                "link_code": st.column_config.LinkColumn(
                    "代码 (Code)", 
                    help="点击查看详情", 
                    display_text=r"code=(.*)$", 
                    width="medium",
                    validate=r"^/\?page=history.*"
                ),
                "symbol_name_show": st.column_config.TextColumn("名称 (Name)", width="medium"),
                "状态": st.column_config.TextColumn("状态 (Status)", width="large"),
                "行情数据日期": st.column_config.TextColumn("行情数据日期 (Market Date)", width="small"),
                "评估日期": st.column_config.TextColumn("评估日期 (Eval Date)", width="small"),
                "评估时间": st.column_config.TextColumn("评估时间 (Eval Time)", width="small"),
                "snapshot_id": None # Hide
            },
            disabled=["link_code", "symbol_name_show", "状态", "行情数据日期", "评估日期", "评估时间"],
            hide_index=True,
            use_container_width=True,
            height=500,
            key="history_mgmt_editor_fixed"
        )

        # Catch selections and show delete button at the top
        selected_rows = edited_df[edited_df["选择 (Select)"] == True]
        if not selected_rows.empty:
            count = len(selected_rows)
            if delete_placeholder.button(f"🗑️ 删除已选 ({count})", type="primary", use_container_width=True):
                success_count = 0
                for sid in selected_rows['snapshot_id']:
                    ok, _ = delete_snapshot(sid)
                    if ok: success_count += 1
                if success_count > 0:
                    st.success(f"✅ 成功删除 {success_count} 条记录")
                    # Clear editor state
                    if "history_mgmt_editor_fixed" in st.session_state:
                        del st.session_state["history_mgmt_editor_fixed"]
                    st.rerun()
                else:
                    st.error("❌ 删除失败，请检查选中条目。")
    else:
        st.warning("暂无历史记录。 / No records found.")

def render_batch_evaluation_dashboard():
    """🗂️ 全量评估面板 (Full Evaluation)"""
    st.markdown("# 🗂️ 全量评估面板")
    st.markdown("### Full Evaluation Dashboard")
    
    st.info("选择市场以全量对本系统内的个股进行评估，并保存结果到历史记录队列。")
    
    st.markdown("##### 选择目标市场 (Select Market)")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.checkbox("🇭🇰 HK (港股)", value=True, key="chk_mkt_hk")
    with col2:
        st.checkbox("🇺🇸 US (美股)", value=False, key="chk_mkt_us")
    with col3:
        st.checkbox("🇨🇳 CN (A股)", value=False, key="chk_mkt_cn")
        
    st.markdown("<div style='height: 10px'></div>", unsafe_allow_html=True)
    
    # 按钮单独放在下一行，宽度适中
    c_btn1, c_btn2, c_btn3 = st.columns([1, 2, 2])
    with c_btn1:
        eval_btn = st.button("🚀 开始全量评估", type="primary", use_container_width=True)
            
    if eval_btn:
        tms = []
        if st.session_state.get("chk_mkt_hk"): tms.append("HK")
        if st.session_state.get("chk_mkt_us"): tms.append("US")
        if st.session_state.get("chk_mkt_cn"): tms.append("CN")
        
        if not tms:
            st.warning("⚠️ 请至少勾选一个市场！")
        else:
            st.session_state.batch_eval_running = tms
        
    if st.session_state.get("batch_eval_running"):
        tms = st.session_state.batch_eval_running
        tm_str = ", ".join(tms)
        st.write(f"正在准备 **{tm_str}** 市场的资产列表...")
        
        from engine.universe_manager import get_universe_assets_v2
        assets = get_universe_assets_v2()
        
        target_assets = [a for a in assets if a.get('market') in tms and a.get('asset_type') in ('EQUITY', 'STOCK')]
        
        if not target_assets:
            st.warning(f"未找到 {tm_str} 市场的个股资产。")
            st.session_state.batch_eval_running = None
            if st.button("确定"):
                st.rerun()
            return
            
        st.write(f"共找到 {len(target_assets)} 个目标资产，开始逐个评估...")
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        error_container = st.empty()
        
        success_count = 0
        error_list = []
        
        from engine.snapshot_builder import run_snapshot
        from datetime import datetime
        eval_date = datetime.now()
        
        for i, a in enumerate(target_assets):
            symbol = a['asset_id']
            name = a.get('symbol_name', '')
            status_text.text(f"正在评估: {symbol} {name}  ({i+1}/{len(target_assets)})")
            try:
                run_snapshot(symbol, as_of_date=eval_date, save_to_db=True)
                success_count += 1
            except Exception as e:
                error_list.append(f"{symbol} {name}: {str(e)}")
                
            progress_bar.progress((i + 1) / len(target_assets))
            
        status_text.text("全量评估完成！")
        if success_count > 0:
            st.success(f"✅ 成功评估了 {success_count} 个资产。")
        if error_list:
            with error_container.container():
                with st.expander("查看失败详情", expanded=True):
                    for err in error_list:
                        st.error(err)
                    
        st.session_state.batch_eval_running = None
        
        def nav_to_history():
            st.session_state.analysis_sub_mode = "📜 评估记录"
            st.session_state.analysis_sub_mode_radio = "📜 评估记录"
            st.query_params["page"] = "history"
            
        st.button("⬅️ 查看评估记录", on_click=nav_to_history)

def main():
    # --- Sidebar: Header ---
    st.sidebar.markdown(
        """
        <a href="/" target="_self">
            <img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAABAAAAAIuCAYAAAAha3r/AAEAAElEQVR4nOz9d5Rd2XXmCe7rnokXFgGbHh7pfSJJuZJKpiQgk6K8qerqmqqpqVWrV01X11Sb1au7/+juNWZ1T9VMT3epDFUSKZEUSZFiJiBPSiRFMr1lOiRMJjLhgXAv4rlrzqzv2+dGAJmBtABeIN7+JYMAIl68d+PFveeevfe3vx0458QwDMMwDMMwDMMwjNVN2O8DMAzDMAzDMAzDMAzj8mMJAMMwDMMwDMMwDMMYACwBYBiGYRiGYRiGYRgDgCUADMMwDMMwDMMwDGMAsASAYRiGYRiGYRiGYQwAlgAwDMMwDMMwDMMwjAHAEgCGYRiGYRiGYRiGMQBYAsAwDMMwDMMwDMMwBgBLABiGYRiGYRiGYRjGAGAJAMMwDMMwDMMwDMMYACwBYBiGYRiGYRiGYRgDgCUADMMwDMMwDMMwDGMAsASAYRiGYRiGYRiGYQwAlgAwDMMwDMMwDMMwjAHAEgCGYRiGYRiGYRiGMQBYAsAwDMMwDMMwDMMwBgBLABiGYRiGYRiGYRjGAGAJAMMwDMMwDMMwDMMYACwBYBiGYRiGYRiGYRgDgCUADMMwDMMwDMMwDGMAsASAYRiGYRiGYRiGYQwAlgAwDMMwDMMwDMMwjAHAEgCGYRiGYRiGYRiGMQBYAsAwDMMwDMMwDMMwBgBLABiGYRiGYRiGYRjGAGAJAMMwDMMwDMMwDMMYACwBYBiGYRiGYRiGYRgDgCUADMMwDMMwDMMwDGMAsASAYRiGYRiGYRiGYQwAlgAwDMMwDMMwDMMwjAHAEgCGYRiGYRiGYRiGMQBYAsAwDMMwDMMwDMMwBgBLABiGYRiGYRiGYRjGAGAJAMMwDMMwDMMwDMMYACwBYBiGYRiGYRiGYRgDgCUADMMwDMMwDMMwDGMAsASAYRiGYRiGYRiGYQwAlgAwDMMwDMMwDMMwjAHAEgCGYRiGYRiGYRiGMQBYAsAwDMMwDMMwDMMwBgBLABiGYRiGYRiGYRjGAGAJAMMwDMMwDMMwDMMYACwBYBiGYRiGYRiGYRgDgCUADMMwDMMwDMMwDGMAsASAYRiGYRiGYRiGYQwAlgAwDMMwDMMwDMMwjAHAEgCGYRiGYRiGYRiGMQBYAsAwDMMwDMMwDMMwBgBLABiGYRiGYRiGYRjGAGAJAMMwDMMwDMMwDMMYACwBYBiGYRiGYRiGYRgDgCUADMMwDMMwDMMwDGMAsASAYRiGYRiGYRiGYQwAlgAwDMMwDMMwDMMwjAHAEgCGYRiGYRiGYRiGMQBYAsAwDMMwDMMwDMMwBgBLABiGYRiGYRiGYRjGAGAJAMMwDMMwDMMwDMMYACwBYBiGYRiGYRiGYRgDgCUADMMwDMMwDMMwDGMAsASAYRiGYRiGYRiGYQwAlgAwDMMwDMMwDMMwjAHAEgCGYRiGYRiGYRiGMQBYAsAwDMMwDMMwDMMwBgBLABiGYRiGYRiGYRjGAGAJAMMwDMMwDMMwDMMYACwBYBiGYRiGYRiGYRgDgCUADMMwDMMwDMMwDGMAsASAYRiGYRiGYRiGYQwAlgAwDMMwDMMwDMMwjAHAEgCGYRiGYRiGYRiGMQBYAsAwDMMwDMMwDMMwBgBLABiGYRiGYRiGYRjGAGAJAMMwDMMwDMMwDMMYACwBYBiGYRiGYRiGYRgDgCUADMMwDMMwDMMwDGMAsASAYRiGYRiGYRiGYQwAlgAwDMMwDMMwDMMwjAHAEgCGYRiGYRiGYRiGMQBYAsAwDMMwDMMwDMMwBgBLABiGYRiGYRiGYRjGAGAJAMMwDMMwDMMwDMMYACwBYBiGYRiGYRiGYRgDgCUADMMwDMMwDMMwDGMAsASAYRiGYRiGYRiGYQwAlgAwDMMwDMMwDMMwjAHAEgCGYRiGYRiGYRiGMQBYAsAwDMMwDMMwDMMwBgBLABiGYRiGYRiGYRjGAGAJAMMwDMMwDMMwDMMYACwBYBiGYRiGYRiGYRgDgCUADMMwDMMwDMMwDGMAsASAYRiGYRiGYRiGYQwAlgAwDMMwDMMwDMMwjAHAEgCGYRiGYRiGYRiGMQBYAsAwDMMwDMMwDMMwBgBLABiGYRiGYRiGYRjGAGAJAMMwDMMwDMMwDMMYACwBYBiGYRiGYRiGYRgDgCUADMMwDMMwDMMwDGMAsASAYRiGYRiGYRiGYQwAlgAwDMMwDMMwDMMwjAHAEgCGYRiGYRiGYRiGMQBYAsAwDMMwDMMwDMMwBgBLABiGYRiGYRiGYRjGAGAJAMMwDMMwDMMwDMMYACwBYBiGYRiGYRiGYRgDgCUADMMwDMMwDMMwDGMAsASAYRiGYRiGYRiGYQwAlgAwDMMwDMMwDMMwjAHAEgCGYRiG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BEEQBMEOIAWAIAiCIAiCIAiCINgBpAAQBEEQBEEQBEEQBDuAFACCIAiCIAiCIAiCYAeQAkAQBEEQBEEQBEEQ7ABSAAiCIAiCIAiCIAiCHUAKAEEQBEEQBEEQBEGwA0gBIAiCIAiCIAiCIAh2ACkABEEQBEEQBEEQBMEOIAWAIAiCIAiCIAiCINgBpAAQBEEQBEEQBEEQBDuAFACCIAiCIAiCIAiCYAeQAkAQBEEQBEEQBEEQ7ABSAAiCIAiCIAiCIAiCHUAKAEEQBEEQBEEQBEGwA0gBIAiCIAiCIAiCIAh2ACkABEEQBEEQBEEQBMEOIAWAIAiCIAiCIAiCINgBpAAQBEEQBEEQBEEQBDuAFACCIAiCIAiCIAiCYAeQAkAQBEEQBEEQBEEQ7ABSAAiCIAiCIAiCIAiCHUAKAEEQBEEQBEEQBEGwA0gBIAiCIAiCIAiCIAh2ACkABEEQBEEQBEEQBMEOIAWAIAiCIAiCIAiCINgBpAAQBEEQBEEQBEEQBDuAFACCIAiCIAiCIAiCYAeQAkAQBEEQBEEQBEEQ7ABSAAiCIAiCIAiCIAiCHUAKAEEQBEEQBEEQBEGwA0gBIAiCIAiCIAiCIAh2ACkABEEQBEEQBEEQBMEOIAWAIAiCIAiCIAiCINgBpAAQBEEQBEEQBEEQBDuAFACCIAiCIAiCIAiCYAeQAkAQBEEQBEEQBEEQ7ABSAAiCIAiCIAiCIAiCHUAKAEEQBEEQBEEQBEGwA0gBIAiCIAiCIAiCIAh2ACkABEEQBEEQBEEQBMEOIAWAIAiCIAiCIAiCINgBpAAQBEEQBEEQBEEQBDuAFACCIAiCIAiCIAiCYAeQAkAQBEEQBEEQBEEQ7ABSAAiCIAiCIAiCIAiCHUAKAEEQBEEQBEEQBEGwA0gBIAiCIAiCIAiCIAh2ACkABEEQBEEQBEEQBMEOIAWAIAiCIAiCIAiCINgBpAAQBEEQBEEQBEEQBDuAFACCIAiCIAiCIAiCYAeQAkAQBEEQBEEQBEEQ7ABSAAiCIAiCIAiCIAiCHUAKAEEQBEEQBEEQBEGwA0gBIAiCIAiCIAiCIAh2ACkABEEQBEEQBEEQBMEOIAWAIAiCIAiCIAiCINgBpAAQBEEQBEEQBEEQBDuAFACCIAiCIAiCIAiCYAeQAkAQBEEQBEEQBEEQ7ABSAAiCIAiCIAiCIAiCHUAKAEEQBEEQBEEQBEGwA0gBIAiCIAiCIAiCIAh2ACkABEEQBEEQBEEQBMEOIAWAIAiCIAiCIAiCINgBpAAQBEEQBEEQBEEQBDuAFACCIAiCIAiCIAiCYAeQAkAQBEEQBEEQBEEQ7ABSAAiCIAiCIAiCIAiCHUAKAEEQBEEQBEEQBEGwA0gBIAiCIAiCIAiCIAh2ACkABEEQBEEQBEEQBMEOIAWAIAiCIAiCIAiCINgBpAAQBEEQBEEQBEEQBO2Nj/8fu+gjJwMNR5gAAAAASUVORK5CYII=" style="width:100%;">
        </a>
        """,
        unsafe_allow_html=True
    )
    st.sidebar.markdown("### Value & Risk Assessment System")
    st.sidebar.caption("资产质量与风险全维深度评估")
    st.sidebar.markdown("---")

    # --- Navigation state: sync with URL query params ---
    NAV_ITEMS = [
        ("welcome",  "🏠 欢迎 (Welcome)"),
        ("analysis", "📊 资产分析 (Analysis)"),
        ("universe", "⚙️ 资产管理 (Universe)"),
        ("import",   "📥 数据导入 (Import)"),
        ("risk",     "🧘 风险自评 (Risk)"),
    ]
    DEFAULT_PAGE_KEY = "welcome"

    nav_keys = [k for k, _ in NAV_ITEMS]
    qp = st.query_params

    # 1) 从 URL → session_state → 默认值 推导当前页面 key
    url_key = None
    if "page" in qp:
        v = qp["page"]
        # 兼容 list / str 两种形式
        if isinstance(v, list):
            url_key = v[0] if v else None
        else:
            url_key = v

    # Special routing: history is a sub-page of analysis
    if url_key == "history":
        current_key = "analysis"
        # Force sub-mode to history
        st.session_state.analysis_sub_mode = "📜 评估记录"
        st.session_state.analysis_sub_mode_radio = "📜 评估记录"
    elif url_key == "batch_eval":
        current_key = "analysis"
        st.session_state.analysis_sub_mode = "🗂️ 全量评估"
        st.session_state.analysis_sub_mode_radio = "🗂️ 全量评估"
    elif url_key in nav_keys:
        current_key = url_key
    else:
        current_key = st.session_state.get("app_mode_key", DEFAULT_PAGE_KEY)

    if current_key not in nav_keys:
        current_key = DEFAULT_PAGE_KEY

    st.session_state.app_mode_key = current_key

    # key -> radio index / label
    key_to_index = {k: i for i, (k, _) in enumerate(NAV_ITEMS)}
    labels = [label for _, label in NAV_ITEMS]
    default_index = key_to_index[current_key]
    label_to_key = {label: key for key, label in NAV_ITEMS}

    # 2) 渲染侧边栏单选，index 与 current_key 对齐
    selected_label = st.sidebar.radio(
        "💡 功能导航",
        labels,
        index=default_index,
        key="nav_radio",
    )
    selected_key = label_to_key.get(selected_label, DEFAULT_PAGE_KEY)

    # 3) 将选择结果同步回 session_state + URL
    if selected_key != current_key:
        st.session_state.app_mode_key = selected_key
        st.session_state.app_mode_label = selected_label
        try:
            # 新版 Streamlit 推荐用法
            st.query_params["page"] = selected_key
        except Exception:
            # 向后兼容
            st.query_params.update(page=selected_key)
    else:
        # 首次运行时确保 label 不为空
        st.session_state.app_mode_label = selected_label

    # 供后面路由逻辑使用（保持原来的字符串比较不变）
    app_mode = st.session_state.app_mode_label

    # --- Notifications from Callbacks (Global) ---
    if "last_save_status" in st.session_state:
        status_type, message = st.session_state.pop("last_save_status")
        if status_type == "success":
            st.success(message)
            st.balloons()
        else:
            st.error(message)

    st.sidebar.markdown("---")

    if app_mode == "🏠 欢迎 (Welcome)":
        render_welcome()
        st.sidebar.markdown("---")
        st.sidebar.info("VERA MVP v0.5\n\nCore Engines: Ready\nDashboard: Connected")
        return

    if app_mode == "⚙️ 资产管理 (Universe)":
        render_asset_management()
        st.sidebar.markdown("---")
        st.sidebar.info("VERA MVP v0.5\n\nCore Engines: Ready\nDashboard: Connected")
        return

    if app_mode == "📥 数据导入 (Import)":
        render_data_import_page()
        return

    if app_mode == "🧘 风险自评 (Risk)":
        render_risk_assessment_page()
        return
    
    # --- 资产分析模式：添加子菜单 ---
    if app_mode == "📊 资产分析 (Analysis)":
        # 初始化子菜单状态
        if "analysis_sub_mode" not in st.session_state:
            st.session_state.analysis_sub_mode = "🗂️ 全量评估"
        
        def on_sub_mode_change():
            """Callback to sync URL params when sub-mode changes"""
            if st.session_state.analysis_sub_mode_radio == "📜 评估记录":
                st.query_params["page"] = "history"
                # If we have a code, keep it in URL so history shows that asset
            elif st.session_state.analysis_sub_mode_radio == "🗂️ 全量评估":
                st.query_params["page"] = "batch_eval"
            else:
                st.query_params["page"] = "analysis"
                # Optional: Clear code if returning to main analysis, or keep it?
                # User might want to analyze the same asset. keeping it seems fine.
                
            # Sync the persistent state variable immediately
            st.session_state.analysis_sub_mode = st.session_state.analysis_sub_mode_radio

        # 显示子菜单
        options = ["🗂️ 全量评估", "📈 单个评估", "📜 评估记录"]
        idx = options.index(st.session_state.analysis_sub_mode) if st.session_state.analysis_sub_mode in options else 0
        analysis_sub_mode = st.sidebar.radio(
            "分析模式",
            options,
            index=idx,
            key="analysis_sub_mode_radio",
            label_visibility="collapsed",
            on_change=on_sub_mode_change
        )
        st.sidebar.markdown("---")
        if analysis_sub_mode == "📜 评估记录":
            # 历史记录页面
            render_history_dashboard()
            return
        if analysis_sub_mode == "🗂️ 全量评估":
            render_batch_evaluation_dashboard()
            return

        # (Removed duplicated Expert Mode logic from here)

    # --- Analysis Mode Logic ---
    if "analysis_active" not in st.session_state:
        st.session_state.analysis_active = False

    # Initialize valuation_last_symbol (STABLE KEY)
    if "valuation_last_symbol" not in st.session_state:
        # Priority: URL > Previous Session State > Default
        url_symbol = st.query_params.get("symbol")
        st.session_state.valuation_last_symbol = url_symbol if url_symbol else "TSLA"

    # Alias to existing symbol_input if needed by other parts of the app
    st.session_state.symbol_input = st.session_state.valuation_last_symbol

    # 1. Fetch Options & Metadata
    universe_df = get_universe_assets_v2()
    universe_ids = [row['asset_id'] for row in universe_df]
    cached_symbols = get_cached_symbols()
    
    # 2. Combine and deduplicate (all are canonical IDs now)
    # Merge universe IDs (ordered by SQL) with cached symbols (extras)
    # CRITICAL: Do NOT use set() or sorted() on the main list, as it destroys the SQL-defined order (HK > US > CN)
    universe_id_set = set(universe_ids)
    extra_ids = [s for s in cached_symbols if s not in universe_id_set]
    all_options = universe_ids + sorted(extra_ids) # Append extras at the end (sorted alphabetically)

    # 4. Initialize Dynamic Search History
    if "recent_searches" not in st.session_state:
        st.session_state.recent_searches = ["BTC/USD", "NVDA", "TSLA", "00700"]

    def update_recent_searches(sym):
        if not sym or sym == "": return
        # Extract pure code if it's canonical
        code = sym.split(':')[-1] if ":" in sym else sym
        
        current = list(st.session_state.recent_searches)
        # Deduplication and insertion at head
        if code in current: current.remove(code)
        current.insert(0, code)
        st.session_state.recent_searches = current[:6]
    
    symbol_map = {row['asset_id']: row.get('symbol_name') for row in universe_df}
    
    # Supplemental fetch for names
    uncached_ids = [s for s in all_options if s not in symbol_map]
    if uncached_ids:
        try:
            conn = get_connection()
            placeholders = ','.join(['?'] * len(uncached_ids))
            rows = conn.execute(f"SELECT asset_id, name FROM assets WHERE asset_id IN ({placeholders})", uncached_ids).fetchall()
            for r in rows:
                if r[1] and r[1] != "-" and r[1] != r[0]:
                    symbol_map[r[0]] = r[1]
            conn.close()
        except: pass

    # 3. Stable Sorting Logic
    asset_meta_map = {row['asset_id']: row for row in universe_df}
    def get_sort_key(s):
        s_u = s.upper()
        meta = asset_meta_map.get(s)
        m_o = 3
        m = meta.get('market') if meta else None
        if not m:
            from engine.asset_resolver import _infer_market
            m = _infer_market(s)
        if m == 'HK': m_o = 0
        elif m == 'US': m_o = 1
        elif m == 'CN': m_o = 2
        
        t_o = 3
        t = meta.get('asset_type') if meta else None
        if not t:
            if (":INDEX:" in s_u or s_u in ['HSI', 'HSTECH', 'SPX', 'NDX', 'DJI']): t = 'INDEX'
            elif (":ETF:" in s_u) or (":STOCK:" in s_u and s_u.split(":")[-1].startswith(("51", "15", "58"))): t = 'ETF'
            else: t = 'EQUITY'
        if t in ['EQUITY', 'STOCK']: t_o = 0  # 个股优先
        elif t == 'ETF': t_o = 1              # ETF次之
        elif t == 'INDEX': t_o = 2            # 指数最后
        
        import re
        d = re.findall(r'\d+', s)
        if d:
            code_part = d[-1]
            if m == 'HK': code_part = code_part.zfill(5)
            try: 
                # Ensure tuple elements are comparable (int vs int)
                # Structure: (Market Priority, Type Priority, IsTextFlag, Value)
                # Value is int here.
                return (m_o, t_o, 0, int(code_part))
            except: pass
        
        # Text Sort (IsTextFlag=1)
        return (m_o, t_o, 1, s_u)


    # all_options = sorted(all_options, key=get_sort_key)
    # Reverting to SQL-based natural order from universe_manager to ensure stability
    pass

    def format_option(s):
        full_name = symbol_map.get(s)
        # Extract pure code (remove prefixes like HK:STOCK:)
        code = s.split(':')[-1]
        
        # Determine valid name
        has_valid_name = full_name and full_name != s and full_name != "-" and not full_name.startswith("HK:")
        
        if has_valid_name:
            clean_name = full_name.replace(f"({code})", "").replace(f"（{code}）", "").strip()
            
            # Anti-duplication logic: if name is effectively the code, return just the code
            # e.g. "AAPL" vs "AAPL", "00700.HK" vs "00700", "600536.SH" vs "600536"
            norm_name = clean_name.upper().replace(".HK", "").replace(".US", "").replace(".CN", "").replace(".SH", "").replace(".SZ", "").replace(".SS", "").strip()
            if norm_name == code.upper():
                return code
                
            return f"{code} {clean_name}"
            
        return code
    
    # --- CSS for Premium Cards ---
    st.markdown("""
    <style>
    /* Card Container Style */
    .vera-card {
        background-color: #1e1e1e;
        border: 1px solid #333;
        border-radius: 12px;
        padding: 24px;
        height: 100%;
    }
    .vera-card-title {
        color: #e5e7eb;
        font-size: 16px;
        font-weight: 600;
        margin-bottom: 20px;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .vera-card-hint {
        color: #6b7280;
        font-size: 12px;
        margin-top: 8px;
        font-style: italic;
    }

    /* AI Banner Style */
    .ai-banner {
        background: linear-gradient(90deg, #1f2937 0%, #111827 100%);
        border: 1px solid #374151;
        border-radius: 8px;
        padding: 12px 20px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 24px;
        cursor: pointer;
        transition: border-color 0.2s;
    }
    .ai-banner:hover {
        border-color: #60a5fa;
    }
    .ai-banner-text {
        color: #e5e7eb;
        font-size: 14px;
        font-weight: 500;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    
    /* Recent Search Tags */
    .tag-container {
        display: flex;
        gap: 8px;
        margin-top: 12px;
        flex-wrap: wrap;
    }
    .search-tag {
        background-color: #374151;
        color: #d1d5db;
        padding: 4px 10px;
        border-radius: 16px;
        font-size: 11px;
        cursor: pointer;
        transition: background-color 0.2s;
        text-decoration: none;
    }
    .search-tag:hover {
        background-color: #4b5563;
        color: #ffffff;
    }
    </style>
    """, unsafe_allow_html=True)

    # --- Header & AI Banner ---
    h_c1, h_c2 = st.columns([0.8, 0.2])
    with h_c1:
         st.markdown("## 📈 资产评估 (Asset Valuation)")
    with h_c2:
         st.markdown(f"<div style='text-align: right; color: #6b7280; font-size: 12px; padding-top: 15px;'>Deploy</div>", unsafe_allow_html=True)

    # AI Banner (Clickable simulation)
    if st.button("✨ 呼唤AI 辅助配置 (Call AI Assistant)", type="secondary", use_container_width=True):
         st.toast("AI 助手正在分析您的偏好... 🚀")
         
    st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)

    # --- Main Cards Layout ---
    # Sync URL
    if st.session_state.get("symbol_input"):
         st.query_params["symbol"] = st.session_state.symbol_input

    c_card_left, c_card_right = st.columns([1.6, 1], gap="large")

    # === Left Card: Asset Selection ===
    with c_card_left:
        with st.container(border=True): # Streamlit native border container for 'Card' feel
             st.markdown("#### 🔍 选择要分析的资产")
             st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
             
             # === ✅ 终极修正方案：URL + Key 绑定法 (Asset Selection) ===
             
             # 1. 确定目标资产 (Target Symbol)
             # 优先级: URL参数 > 历史记忆 (Session) > 默认第一个
             target_symbol = None
             
             # (A) 尝试从 URL 获取
             # (A) 尝试从 URL 获取
             if "symbol" in st.query_params:
                 url_val = st.query_params["symbol"]
                 # 兼容列表或单值
                 url_str = url_val if isinstance(url_val, str) else url_val[0]
                 if url_str:
                     target_symbol = url_str
             
             # (B) 如果 URL 没指定，看 Session State (Asset Select)
             if not target_symbol and st.session_state.get("asset_select") in all_options:
                 target_symbol = st.session_state["asset_select"]

             # (C) 兼容旧 key & 默认值
             if not target_symbol:
                  if st.session_state.get("valuation_last_symbol"):
                      target_symbol = st.session_state["valuation_last_symbol"]
                  elif all_options:
                      target_symbol = all_options[0]
 
             # 2. 关键步骤：同步状态
             if target_symbol:
                 # Ensure target is in options so selectbox can select it
                 if target_symbol not in all_options:
                     all_options.insert(0, target_symbol)
                     
                     # Try to fetch name for this ad-hoc symbol so it displays nicely
                     if target_symbol not in symbol_map:
                         try:
                             with sqlite3.connect("vera.db") as conn:
                                 r = conn.execute("SELECT name FROM assets WHERE asset_id = ?", (target_symbol,)).fetchone()
                                 if r and r[0] and r[0] != "-" and r[0] != target_symbol:
                                     symbol_map[target_symbol] = r[0]
                         except: pass

                 # Sync to Dropdown
                 st.session_state["asset_select"] = target_symbol 
                 
                 # 始终同步给文本框和其他状态
                 st.session_state.valuation_last_symbol = target_symbol
                 st.session_state.symbol_input = target_symbol
                 # Force update text input to match URL even if not in dropdown
                 st.session_state.text_input_symbol = target_symbol

             # 3. 定义回调 (当用户手动改变选项时触发)
             def on_asset_change():
                 selected = st.session_state.asset_select
                 # 立即把新选择写入 URL -> 实现 F5 刷新依然保留
                 st.query_params["symbol"] = selected
                 
                 # 同步到其他状态
                 st.session_state.valuation_last_symbol = selected
                 st.session_state.symbol_input = selected
                 st.session_state.text_input_symbol = selected # 同步文本框
                 st.session_state.recent_pills = None # 清除 Pills 状态
                 
                 # 触发业务逻辑更新 (如最近搜索记录)
                 update_recent_searches(selected)

             # 4. 渲染 Selectbox (抛弃 index 参数!)
             st.selectbox(
                 "从资产库中选择 (Select from Universe)",
                 options=all_options,
                 format_func=format_option,
                 key="asset_select", # 核心：绑定 Session Key，Streamlit 会自动选中对应项
                 on_change=on_asset_change,
                 label_visibility="collapsed"
             )
             st.caption("从资产库中选择 (Select from Universe)")

             st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
             
             # 2. Text Input (Fallback / Direct Entry)
             # Sync Text Input Display with target_symbol
             if "text_input_symbol" not in st.session_state:
                 st.session_state.text_input_symbol = target_symbol if target_symbol else ""
             
             # Defensive sync: if text input visually lags behind main symbol
             if st.session_state.text_input_symbol != target_symbol:
                  st.session_state.text_input_symbol = target_symbol

             def on_text_input_change():
                 val = st.session_state.text_input_symbol
                 st.session_state.asset_select = val # 反向同步给 Dropdown
                 st.session_state.valuation_last_symbol = val
                 st.session_state.symbol_input = val
                 st.query_params["symbol"] = val
                 st.session_state.recent_pills = None
                 update_recent_searches(val)

             st.text_input(
                "或直接输入资产代码 (Or enter Symbol)", 
                placeholder="例如: HK:STOCK:00700",
                key="text_input_symbol", 
                on_change=on_text_input_change,
                label_visibility="collapsed"
             )
             
             # Ensure 'symbol' variable is defined for downstream logic
             symbol = st.session_state.get("text_input_symbol", target_symbol).upper().strip()
             st.caption("或直接输入资产代码 (Or enter Symbol)")
             
             # 3. Recent Search Tags (Interactive using pills)
             st.markdown("<div style='color: #4b5563; font-size: 11px; margin-top: 6px; margin-bottom: 8px;'>最近搜索 (RECENTLY SEARCHED)</div>", unsafe_allow_html=True)
             
             recent_tags = st.session_state.recent_searches
             
             # Use buttons instead of pills for reliable click-to-search action
             if recent_tags:
                 # Define callback to update state BEFORE widget instantiation on rerun
                 def _update_search(t):
                     st.session_state.text_input_symbol = t
                     st.session_state.valuation_last_symbol = t
                     st.query_params["symbol"] = t

                 # Grid Layout: Max 4 buttons per row to ensure enough width
                 MAX_COLS = 4
                 
                 # Chunk list into rows
                 rows = [recent_tags[i:i + MAX_COLS] for i in range(0, len(recent_tags), MAX_COLS)]
                 
                 for row_idx, row_tags in enumerate(rows):
                     cols = st.columns(MAX_COLS)
                     for i, tag in enumerate(row_tags):
                         cols[i].button(
                             tag, 
                             key=f"btn_recent_{row_idx}_{i}_{tag}", 
                             help=f"Search {tag}",
                             on_click=_update_search,
                             args=(tag,),
                             use_container_width=True
                         )

    # === Right Card: Settings ===
    with c_card_right:
        with st.container(border=True):
             st.markdown("#### 🗓️ 时间与参数配置")
             st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True)

             st.label_visibility = "visible"
             
             if "eval_date" not in st.session_state: st.session_state.eval_date = datetime.now()
             def set_today(): st.session_state.eval_date = datetime.now()

             # Date Inputs aligned
             cd1, cd2 = st.columns([2, 1])
             with cd1:
                 eval_date = st.date_input("评估基准日 (As of Date)", key="eval_date")
             with cd2:
                 st.markdown("<div style='height: 1.8rem;'></div>", unsafe_allow_html=True)
                 st.button("最近交易日", use_container_width=True, on_click=set_today)

             st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
             
             # Chart Range Filters (Restored)
             with st.expander("📊 图表时间范围 (Chart Range)", expanded=False):
                cd_r1, cd_r2 = st.columns(2)
                with cd_r1:
                    chart_start = st.date_input("开始 (Start)", value=None, key="chart_start")
                with cd_r2:
                    chart_end = st.date_input("结束 (End)", value=None, key="chart_end")

             st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
             
             # Expert Mode Toggle (Moved from Sidebar)
             st.toggle("🔬 开启专家模式 (Expert Mode)", key="expert_mode_active", help="开启后展示底层判定依据与穿透审计面板")
             
             # NEW: Global AI CapEx Risk Toggle (As requested by user via image)
             st.toggle("🚀 全局 AI 风险强制评估", key="ai_capex_forced_active", help="开启后，系统将对所有个股尝试运行 AI CapEx 风险评估模块，无视行业和标签限制（需具备基本 CapEx 数据）。")
             
             st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
             st.markdown("<div style='text-align: center; color: #6b7280; font-size: 12px; font-style: italic;'>系统将根据基准日自动获取最新的市场估值乘数与财报数据。</div>", unsafe_allow_html=True)

    st.markdown("<div style='height: 30px;'></div>", unsafe_allow_html=True)

    # --- Action Area ---
    # Centered Big Button
    c_act1, c_act2, c_act3 = st.columns([1, 2, 1])
    with c_act2:
        run_btn = st.button("🚀 运行分析 (Run Analysis)", type="primary", use_container_width=True)
    
    
    st.markdown("<div style='height: 50px;'></div>", unsafe_allow_html=True)

    

    
    # 更新 session state
    if run_btn:
        st.session_state.analysis_active = True
        st.session_state.valuation_last_symbol = symbol
        st.session_state.symbol_input = symbol
        st.query_params["symbol"] = symbol


    if not st.session_state.analysis_active:
        # 显示提示信息 (Only when not analyzing)
        st.info("ℹ️ 请从上方选择或输入资产代码，然后点击「运行分析」按钮开始评估。系统将根据您的历史搜索偏好自动匹配最优算法。")
        return
    else:
        if not symbol:
            st.warning("请输入代码 / Please enter a symbol.")
            st.session_state.analysis_active = False
            return
            
        try:
            data: DashboardData = run_snapshot(symbol, as_of_date=eval_date)
            
            # Cache audit data for sidebar usage
            if data and data.expert_audit:
                st.session_state.last_audit_data = data.expert_audit

            if not data:
                st.error(f"无法获取 {symbol} 在 {eval_date.strftime('%Y-%m-%d')} 之前的数据。")
                if st.button("返回历史记录"):
                    st.session_state.analysis_active = False
                    st.rerun()
                return
            
            # Duplicate buttons removed (handled in Header)

            render_page(data, chart_start_date=chart_start, chart_end_date=chart_end)
            
            # Global Footer for Expert Mode
            if st.session_state.get("expert_mode_active"):
                st.markdown("""
                <div style="text-align:center; padding:20px; color:#3b82f6; font-size:0.8rem; opacity:0.6;">
                    --- 🛡️ EXPERT AUDIT MODE ACTIVE | FULL TRANSPARENCY ENABLED ---
                </div>
                """, unsafe_allow_html=True)

        except Exception as e:
            st.error(f"分析异常: {str(e)}")
            st.session_state.analysis_active = False

if __name__ == "__main__":
    main()
