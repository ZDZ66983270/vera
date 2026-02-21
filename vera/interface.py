# vera/interface.py

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from vera.config.thresholds import VOL_ANNUALIZATION_DAYS
from vera.engines.underlying_regime_engine import UnderlyingRegimeEngine
from vera.engines.options_state_engine import OptionsStateEngine
from vera.engines.permission_engine import PermissionEngine
from vera.mappings import get_u_state_cn, get_o_state_cn, get_r_state_cn, get_action_cn
from data.price_cache import load_price_series

def get_vera_verdict(symbol: str, anchor_date: str = None) -> dict:
    """
    Main entry point for UI/API.
    Fetches data, runs engines, returns transparent decision object.
    
    anchor_date: The baseline date for assessment (str or date). 
                 If None, uses today.
    """
    
    # 1. Fetch Data (last 365 days to ensure enough history for MA/Vol/IV)
    if anchor_date is None:
        end_dt = datetime.today()
    elif isinstance(anchor_date, str):
        end_dt = datetime.strptime(anchor_date, '%Y-%m-%d')
    else:
        # Assume it's a date or datetime object (e.g. from streamlit)
        end_dt = datetime.combine(anchor_date, datetime.min.time()) if not isinstance(anchor_date, datetime) else anchor_date

    end_date_str = end_dt.strftime('%Y-%m-%d')
    start_date_str = (end_dt - timedelta(days=365)).strftime('%Y-%m-%d')
    
    df = load_price_series(symbol, start_date_str, end_date_str)
    
    # Validation
    if df.empty or len(df) < 60:
         return _get_error_response(symbol, "Insufficient price history (<60 days)")

    # 2. Preprocessing (Compute Inputs for VERA)
    df = df.sort_values("trade_date")
    # Simple Returns for UI/Legacy compatibility
    df["ret"] = df["close"].pct_change()
    # Log Returns for Robustness
    df["log_ret"] = np.log(df["close"] / df["close"].shift(1))
    
    # Volume Ratio Baseline: 20-day Moving Average (MA20)
    df["vol_ma20"] = df["volume"].rolling(20).mean()
    
    # Real Calculation: Annualized Historical Volatility (20-day)
    # Using HV as a sophisticated surrogate for IV when real option data is missing
    # Rename to recognized_vol_20d or similar
    df["hv20_annualized"] = df["log_ret"].rolling(20).std() * np.sqrt(VOL_ANNUALIZATION_DAYS)
    
    # Proxy Series (Fallback to 25% only for first 20 days)
    vol_series = df["hv20_annualized"].fillna(0.25)
    vol_source = "proxy_hv20" # Explicitly mark as proxy
    
    # 3. Instantiate Engines
    u_engine = UnderlyingRegimeEngine()
    o_engine = OptionsStateEngine()
    p_engine = PermissionEngine()

    # 4. Evaluate
    u_out = u_engine.evaluate(df)
    o_out = o_engine.evaluate(vol_series, source=vol_source)

    decision = p_engine.evaluate(
        U_state=u_out["U_state"],
        O_state=o_out["O_state"]
    )
    

    # 5. Translate & Format Output (The "Product" Layer)
    
    # --- Logic for UI Enhancements (Constraints, Conditions, Reasons) ---
    
    # A. Evidence (Fact-based Alerts) - "Triggered Facts"
    evidence = []
    metrics = u_out.get("metrics", {})
    daily_ret = metrics.get('daily_ret', 0)
    vol_ratio = metrics.get('vol_ratio', 0)
    close_pos = metrics.get('close_pos', 0)
    is_new_low = metrics.get('new_low', False)
    
    # Fact-based tags based on metrics (regardless of state, simply facts)
    if is_new_low: evidence.append(f"创3日新低 ({daily_ret:.1%})")
    if vol_ratio >= 1.5: evidence.append(f"量比异常: {vol_ratio:.1f}x")
    if close_pos <= 0.2: evidence.append(f"收盘极弱: {close_pos:.0%}")
    elif close_pos >= 0.8: evidence.append(f"收盘极强: {close_pos:.0%}")
    if daily_ret < -0.03: evidence.append(f"大跌: {daily_ret:.1%}")
    
    # B. Constraints / Risk Tags (Map to internal codes for UI mapping)
    # Mapping to: ["CIRCUIT_BREAKER", "EXTREME_VOL", "TREND_UNSTABLE", "LOW_MOMENTUM", "HIGH_PREMIUM"]
    u_state = u_out["U_state"]
    r_state = decision["R_state"]
    risk_tags = []
    constraints = [] # Define for legacy compatibility in return dict
    if r_state == "RED":
        risk_tags.append("CIRCUIT_BREAKER")
    
    if u_state == "U3_DISCOVERY":
        risk_tags.append("EXTREME_VOL")
        risk_tags.append("TREND_UNSTABLE")
    elif u_state == "U4_STABILIZATION":
         risk_tags.append("LOW_MOMENTUM")
    
    if o_out["O_state"] == "O1_IV_EXPANSION":
        risk_tags.append("HIGH_PREMIUM")

    # C. Next Conditions with Progress (Checklist)
    # Define thresholds
    TARGET_VOL = 1.5
    TARGET_POS = 0.55
    
    # C. Next Conditions with Progress (Checklist)
    # Define thresholds
    TARGET_VOL = 1.5
    TARGET_POS = 0.55
    
    next_conditions_details = []
    
    # 1. New Low Check
    if is_new_low:
        # We can detect if it was a close low or price low for evidence
        ev_msg = "收盘或最低点下行"
        next_conditions_details.append({
            "label": "不创新低 (最近 3 日)", 
            "status": "❌", 
            "value": "出现新低", 
            "target": "站稳上日低位",
            "evidence": ev_msg
        })
    else:
        next_conditions_details.append({
            "label": "不创新低 (最近 3 日)", 
            "status": "✅", 
            "value": "已站稳", 
            "target": "站稳",
            "evidence": "价格未突破前低"
        })
        
    # 2. Volume Check
    v_status = "❌" if vol_ratio > TARGET_VOL else "✅"
    next_conditions_details.append({
        "label": f"成交量需回归常态 (<{TARGET_VOL}x)", 
        "status": v_status, 
        "value": f"{vol_ratio:.1f}x", 
        "target": f"<{TARGET_VOL}x",
        "evidence": f"当日量比 {vol_ratio:.1f}x"
    })
        
    # 3. Close Position (Strength)
    cp_status = "❌" if close_pos < TARGET_POS else "✅"
    next_conditions_details.append({
        "label": f"收盘价重回区间 {TARGET_POS:.0%} 之上", 
        "status": cp_status, 
        "value": f"{close_pos:.0%}", 
        "target": f">{TARGET_POS:.0%}",
        "evidence": f"收盘位置 {close_pos:.0%}"
    })

    # D. Action Reasons (Short Tags)
    allowed_actions = decision["allowed_actions"]
    action_reasons = {}
    
    # Default tags based on R_state/U_state
    roll_tag = "风险"
    csp_tag = "激进"
    buy_tag = "需确认"
    
    if r_state == "RED":
        roll_tag = "禁操作"
        csp_tag = "禁开仓"
        buy_tag = "禁买入"
    elif r_state == "GREEN":
        roll_tag = "可降本"
        csp_tag = "高胜率"
        buy_tag = "右侧参与"
    elif r_state == "YELLOW":
        roll_tag = "观察"
        csp_tag = "轻仓"
        buy_tag = "暂不买入"
    
    action_reasons["roll_put"] = roll_tag
    action_reasons["sell_put_csp"] = csp_tag
    action_reasons["buy_underlying"] = buy_tag

    # Translate specific fields
    decision_cn = {
        "R_state": decision["R_state"],
        "R_state_label": get_r_state_cn(decision["R_state"]),
        "summary_label_zh": decision.get("summary_label_zh", get_r_state_cn(decision["R_state"])),
        "summary_note_zh": decision.get("summary_note_zh", ""),
        "allowed_actions": allowed_actions,
        "action_reasons": action_reasons, 
        "risk_tags": risk_tags,           # New Code-based Tags
        "constraints": constraints,       # Legacy (to be removed in UI if preferred)
        "reason": get_action_cn(decision.get("reason", "")), 
        "evidence": evidence,             # Fact-based
        "next_conditions_details": next_conditions_details,
        "next_conditions": [c["label"] for c in next_conditions_details if c["status"] == "❌"] 
    }

    return {
        "symbol": symbol,
        "asof": df.iloc[-1]["trade_date"] if "trade_date" in df.columns else end_date,
        "model_version": "vera-core@0.1.0",
        "threshold_profile": "default_v1",
        "underlying": {
            "U_state": u_out["U_state"],
            "U_state_label": get_u_state_cn(u_out["U_state"]),
            "metrics": u_out.get("metrics")
        },
        "options": {
            "O_state": o_out["O_state"],
            "O_state_label": get_o_state_cn(o_out["O_state"]),
            "iv_now": o_out.get("iv_now"),
            "iv_now_pct": o_out.get("iv_now_pct"),
            "vol_source": o_out.get("vol_source", "proxy_hv20"), # Pass through source
            "metrics": o_out.get("metrics")
        },
        "decision": decision_cn
    }

def _get_error_response(symbol, message):
    return {
        "symbol": symbol,
        "error": message,
        "decision": {
            "R_state": "UNKNOWN",
            "allowed_actions": {}
        }
    }
