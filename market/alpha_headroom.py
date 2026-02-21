
# market/alpha_headroom.py

BASE = {"I1":"High","I2":"High","I3":"Medium","I4":"Low","I5":"None"}
ORDER = ["None","Low","Medium","High"]

def _downgrade(level: str, at_most: str) -> str:
    return ORDER[min(ORDER.index(level), ORDER.index(at_most))]

def _narr(level: str) -> str:
    if level == "High":
        return "市场环境较为健康，个股分化空间较大，价格更可能反映公司差异而非系统性压力。"
    if level == "Medium":
        return "市场存在一定压力，个股分化空间下降；选股逻辑仍可能有效，但更依赖风险控制与节奏。"
    if level == "Low":
        return "市场处于系统性压力阶段，个股分化空间较低；短期价格更可能由风险偏好与流动性驱动。"
    return "市场处于极端风险阶段，个股分化空间可能接近消失；相关性上升使得多数资产呈现同涨同跌特征。"

def compute_alpha_headroom(index_state: str, amplification_level: str):
    level = BASE.get(index_state, "Medium")
    if amplification_level == "High":
        level = _downgrade(level, "Medium")
    elif amplification_level == "Extreme":
        level = _downgrade(level, "Low")

    return {
        "alpha_headroom": level,
        "rationale_code": f"AHM_V1:{index_state}+{amplification_level}",
        "notes": [_narr(level)]
    }
