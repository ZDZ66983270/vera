# analysis/quality_overlay_rules.py
from __future__ import annotations
from typing import Optional, Dict, Any

def quality_risk_interaction_flag(
    *,
    dd_state: Optional[str],
    quality_buffer_level: Optional[str],
) -> Optional[Dict[str, Any]]:
    """
    对齐你的系统：
    - flag_level: ALERT/WARN/INFO
    - flag_dimension: QUALITY
    """

    if not dd_state or not quality_buffer_level:
        return None

    s = dd_state.strip().upper()
    q = quality_buffer_level.strip().upper()

    high_risk = s in {"D3", "D4", "D5"}
    if not high_risk:
        return None

    # 1) D4/D5 + WEAK => ALERT
    if s in {"D4", "D5"} and q == "WEAK":
        return {
            "flag_code": "QUALITY_RISK_ALERT",
            "flag_level": "ALERT",
            "flag_dimension": "QUALITY",
            "flag_title": "质量缓冲不足，回撤风险可能非线性放大",
            "flag_description": "当前处于敏感/脆弱回撤阶段（D4/D5），且质量缓冲为 WEAK。建议降低操作频率，避免追涨杀跌，并关注现金流/负债与治理变化信号。"
        }

    # 2) D3 + WEAK => WARN
    if s == "D3" and q == "WEAK":
        return {
            "flag_code": "QUALITY_RISK_WARN",
            "flag_level": "WARN",
            "flag_dimension": "QUALITY",
            "flag_title": "深度回撤 + 质量偏弱",
            "flag_description": "当前处于 D3 且质量缓冲 WEAK。此阶段容易出现\"弱反弹后再下探\"的路径，请把仓位与止损/加仓纪律前置。"
        }

    # 3) D3/D4/D5 + MODERATE => INFO（可选但建议开启）
    if q == "MODERATE":
        return {
            "flag_code": "QUALITY_RISK_INFO",
            "flag_level": "INFO",
            "flag_dimension": "QUALITY",
            "flag_title": "风险阶段已进入深水区，请复核质量缓冲",
            "flag_description": "当前处于 D3-D5，质量缓冲为 MODERATE。建议复核资产负债表与现金流代理指标是否缺失，以及是否存在稀释/资本分配不一致的迹象。"
        }

    return None

def valuation_quality_interaction_flag(
    *,
    valuation_status: str,  # Undervalued, Fair, Overvalued, Extreme
    quality_buffer_level: Optional[str],
) -> Optional[Dict[str, Any]]:
    """
    估值-质量联动规则
    """
    if not valuation_status or not quality_buffer_level:
        return None
        
    v = valuation_status.strip() # Case sensitive usually, but let's assume standard format
    q = quality_buffer_level.strip().upper()
    
    # 1. Bubble Risk (High Val + Weak Quality)
    if v in ("Overvalued", "Extreme") and q == "WEAK":
        return {
            "flag_code": "VALUATION_BUBBLE_RISK",
            "flag_level": "ALERT", # High risk
            "flag_dimension": "VALUATION",
            "flag_title": "泡沫风险警示",
            "flag_description": f"当前估值状态为 {v}，但质量缓冲仅为 WEAK。典型的价值陷阱或泡沫特征，建议极大降低仓位或回避。"
        }
        
    # 2. Patience Zone (Low Val + Strong Quality)
    if v == "Undervalued" and q == "STRONG":
        return {
            "flag_code": "VALUATION_PATIENCE_ZONE",
            "flag_level": "INFO", # Opportunity/Positive
            "flag_dimension": "VALUATION",
            "flag_title": "黄金坑/耐心区",
            "flag_description": "当前处于低估值区间且质量缓冲强劲 (STRONG)。具备极高的长期安全边际，建议结合技术面右侧信号分批布局。"
        }
        
    return None
