
# market/amplifier.py

LEVELS = {
    ("D1","I1"):"Low", ("D1","I2"):"Low", ("D1","I3"):"Medium", ("D1","I4"):"High", ("D1","I5"):"Extreme",
    ("D2","I1"):"Low", ("D2","I2"):"Medium", ("D2","I3"):"High", ("D2","I4"):"Extreme", ("D2","I5"):"Extreme",
    ("D3","I1"):"Medium", ("D3","I2"):"High", ("D3","I3"):"Extreme", ("D3","I4"):"Extreme", ("D3","I5"):"Extreme",
    ("D4","I1"):"Low", ("D4","I2"):"Low", ("D4","I3"):"Low", ("D4","I4"):"Extreme", ("D4","I5"):"Extreme",
    ("D5","I1"):"Low", ("D5","I2"):"Low", ("D5","I3"):"Low", ("D5","I4"):"Extreme", ("D5","I5"):"Extreme",
}

DISABLE = {("D4","I1"),("D4","I2"),("D4","I3"),("D5","I1"),("D5","I2"),("D5","I3")}

def _narr(level: str) -> str:
    if level == "Low":
        return "市场环境对个股风险的放大效应较弱，价格行为更可能由个股自身驱动。"
    if level == "Medium":
        return "市场风险处于可感知水平，可能放大个股的波动与回撤体验。"
    if level == "High":
        return "市场环境可能显著放大个股风险，修复过程更易出现中断与反复。"
    return "市场处于系统性压力阶段，个股间相关性上升，价格波动可能主要反映流动性与风险偏好收缩。"

def _disabled_narr() -> str:
    return "个股当前处于风险释放阶段；在该阶段，市场环境不足以解释或缓解个股自身风险结构。"

def compute_market_amplifier(stock_state: str, index_state: str, index_symbol: str):
    key = (stock_state, index_state)
    disabled = key in DISABLE
    level = LEVELS.get(key, "Medium")

    return {
        "index_symbol": index_symbol,
        "index_risk_state": index_state,
        "amplification_level": ("Low" if disabled else level),
        "disabled": disabled,
        "rationale_code": f"MA_MATRIX_V1:{stock_state}x{index_state}",
        "notes": [_disabled_narr() if disabled else _narr(level)]
    }
