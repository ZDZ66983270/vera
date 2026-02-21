# analysis/risk_quadrant.py
"""
VERA Position Risk & Quadrant 计算模块

核心设计原则：
1. Quadrant 只能由二值 bin 决定（pos_bin × path_bin）
2. UI 只展示后端结果，不再"前端推导"
3. 滞回防抖机制避免边界频繁切换
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class PositionRiskResult:
    """Position Risk 计算结果"""
    price_percentile: Optional[float]    # 0..1 价格分位
    pos_bin: str                          # "HIGH" | "LOW"
    path_bin: str                         # "HIGH" | "LOW"
    risk_quadrant: str                    # "Q1".."Q4"
    notes: Dict[str, Any]                 # 解释信息（如 hysteresis, dd_state）


def _bin_position(price_percentile: Optional[float],
                  *,
                  enter_high: float = 0.62,
                  exit_high: float = 0.58,
                  last_pos_bin: Optional[str] = None) -> str:
    """
    二值化位置（带滞回，防抖）
    
    Args:
        price_percentile: 价格分位 (0..1)
        enter_high: 进入 HIGH 的阈值
        exit_high: 退出 HIGH 的阈值
        last_pos_bin: 上一次的 bin 结果（用于滞回）
    
    Returns:
        "HIGH" 或 "LOW"
    
    逻辑：
    - 从 LOW → HIGH：需要超过 62%
    - 从 HIGH → LOW：需要低于 58%
    - 无历史时：用 60% 作为稳健阈值
    """
    if price_percentile is None:
        return "LOW"

    if last_pos_bin == "HIGH":
        return "HIGH" if price_percentile >= exit_high else "LOW"
    if last_pos_bin == "LOW":
        return "HIGH" if price_percentile >= enter_high else "LOW"

    # 没有历史时用稳健阈值
    return "HIGH" if price_percentile >= 0.60 else "LOW"


def _bin_path_from_dd_state(dd_state: Optional[str]) -> str:
    """
    二值化路径（结构）
    
    Args:
        dd_state: D-state (D0-D5)
    
    Returns:
        "HIGH" 或 "LOW"
    
    规则：
    - D0/D1/D2：结构相对稳（LOW）
    - D3/D4/D5/D6：结构脆弱或深度危机（HIGH）
    """
    if not dd_state:
        return "LOW"
    s = dd_state.strip().upper()
    return "HIGH" if s in {"D3", "D4", "D5", "D6"} else "LOW"


def _quadrant_from_bins(pos_bin: str, path_bin: str) -> str:
    """
    2x2 Quadrant 定义（冻结为 v1.0 标准）
    
    Args:
        pos_bin: Position bin ("HIGH" | "LOW")
        path_bin: Path bin ("HIGH" | "LOW")
    
    Returns:
        "Q1" | "Q2" | "Q3" | "Q4"
    
    映射规则：
    - HIGH + LOW  → Q1 (追涨区)
    - HIGH + HIGH → Q2 (泡沫区)
    - LOW  + HIGH → Q3 (恐慌区)
    - LOW  + LOW  → Q4 (稳态区)
    """
    if pos_bin == "HIGH" and path_bin == "LOW":
        return "Q1"
    if pos_bin == "HIGH" and path_bin == "HIGH":
        return "Q2"
    if pos_bin == "LOW" and path_bin == "HIGH":
        return "Q3"
    return "Q4"


def compute_position_risk(price_percentile: Optional[float],
                          dd_state: Optional[str],
                          *,
                          last_pos_bin: Optional[str] = None) -> PositionRiskResult:
    """
    统一计算 Position Risk 与 Quadrant
    
    Args:
        price_percentile: 价格历史分位 (0..1)
        dd_state: D-state (D0-D5)
        last_pos_bin: 上一次的 position bin（用于滞回）
    
    Returns:
        PositionRiskResult 包含所有计算结果
    
    示例：
        >>> result = compute_position_risk(0.65, "D2")
        >>> result.pos_bin  # "HIGH"
        >>> result.path_bin  # "LOW"
        >>> result.risk_quadrant  # "Q1"
    """
    pos_bin = _bin_position(price_percentile, last_pos_bin=last_pos_bin)
    path_bin = _bin_path_from_dd_state(dd_state)
    quad = _quadrant_from_bins(pos_bin, path_bin)

    return PositionRiskResult(
        price_percentile=price_percentile,
        pos_bin=pos_bin,
        path_bin=path_bin,
        risk_quadrant=quad,
        notes={
            "dd_state": dd_state,
            "hysteresis": {
                "enter_high": 0.62,
                "exit_high": 0.58
            }
        }
    )


def validate_risk_card_display(risk_card: Dict[str, Any]) -> Dict[str, list]:
    """
    风险展示一致性校验规则
    
    验证 risk_card 是否满足 UI 显示规范，返回违规项。
    
    Args:
        risk_card: 风险卡数据字典
    
    Returns:
        违规项字典 {"errors": [...], "warnings": [...]}
    
    校验规则：
    - R1: Quadrant 必须来自后端
    - R2: 百分比与风险等级不得矛盾
    - R3: D0 不得触发"高风险措辞"
    - R4: Path 与 Position 不得互相越权
    - R5: 缺失值不得用 0 代替
    """
    errors = []
    warnings = []
    
    # R1: Quadrant 必须存在
    if "risk_quadrant" not in risk_card or not risk_card["risk_quadrant"]:
        errors.append("R1: risk_quadrant 缺失，前端不得自行推导")
    
    # R2: 百分比与风险等级一致性
    path_risk = risk_card.get("path_risk_level")
    dd_state = risk_card.get("path_state")
    
    if path_risk == "HIGH" and dd_state == "D0":
        warnings.append("R2: path_risk_level=HIGH 但 D-state=D0（结构信息不足）可能存在语义矛盾")
    
    # R3: D0 安全性检查
    if dd_state == "D0":
        # 检查 notes/description 中是否有过强判断
        desc = risk_card.get("path_interpretation", "").lower()
        risky_terms = ["bubble", "panic", "二次探底", "修复失败"]
        for term in risky_terms:
            if term in desc:
                errors.append(f"R3: D0 状态下不得出现'{term}'等强判断措辞")
    
    # R5: 缺失值检查
    percentile = risk_card.get("price_percentile")
    if percentile == 0.0:
        warnings.append("R5: price_percentile=0.0，请确认是真实值而非缺失值代替")
    
    return {
        "errors": errors,
        "warnings": warnings
    }


def generate_behavior_flags(quadrant: str, dd_state: Optional[str] = None, pos_bin: str = None, path_bin: str = None) -> list:
    """
    根据 Quadrant + D-state 生成 Behavior Flags (v2.0)
    
    Args:
        quadrant: Risk Quadrant (Q1-Q4)
        dd_state: D-state for refinement (D0-D5)
        pos_bin: Position bin for verification (HIGH/LOW)
        path_bin: Path bin for verification (HIGH/LOW)
    
    Returns:
        List of behavior flag dicts
    
    设计原则：
    - Quadrant 决定基础 flag
    - dd_state 细化描述强度/紧迫性
    - 确保与象限标签（追涨区/稳态区）永久一致
    """
    flags = []
    
    # Q1: 追涨区 (HIGH Position + LOW Path)
    if quadrant == "Q1":
        base_flag = {
            "code": "FOMO_RISK",
            "level": "WARN",
            "dimension": "POSITION",
            "title": "追涨风险 (FOMO)",
            "description": "价格处于历史高位且结构尚稳，最容易诱发'不买就错过'的过度乐观心理。"
        }
        
        # D-state 细化
        if dd_state == "D2":
            base_flag["description"] += " 当前处于结构中性阶段，警惕向D3转移。"
        elif dd_state in ["D0", "D1"]:
            base_flag["description"] += " 结构波动小，但高位风险依然存在。"
        
        flags.append(base_flag)
    
    # Q2: 泡沫区 (HIGH Position + HIGH Path)
    elif quadrant == "Q2":
        base_flag = {
            "code": "OVERCONFIDENCE_RISK",
            "level": "ALERT",
            "dimension": "COMBINED",
            "title": "情绪坍塌风险",
            "description": "高位叠加结构脆弱。此时极易发生'由于不愿承认行情结束而导致的深度套牢'。"
        }
        
        # D-state 细化（Q2 是最危险的象限）
        if dd_state == "D5":
            base_flag["level"] = "CRITICAL"
            base_flag["description"] += " ⚠️ D5脆弱阶段，风险极高！"
        elif dd_state == "D4":
            base_flag["description"] += " D4敏感阶段，需要严格止损纪律。"
        elif dd_state == "D3":
            base_flag["description"] += " D3博弈区，形势不明朗。"
        
        flags.append(base_flag)
    
    # Q3: 恐慌区 (LOW Position + HIGH Path)
    elif quadrant == "Q3":
        base_flag = {
            "code": "PANIC_SELL_RISK",
            "level": "WARN",
            "dimension": "PATH",
            "title": "杀跌风险 (PANIC)",
            "description": "价格已在低位但波动依旧剧烈，极易在黎明前夕因为生理性恐慌而错误离场。"
        }
        
        # D-state 细化
        if dd_state == "D5":
            base_flag["description"] += " D5阶段恐慌情绪最浓，需要强大心理素质。"
        elif dd_state == "D4":
            base_flag["description"] += " D4阶段，结构未稳定前不宜过度乐观。"
        
        flags.append(base_flag)
    
    # Q4: 稳态区 (LOW Position + LOW Path)
    elif quadrant == "Q4":
        base_flag = {
            "code": "FALSE_SECURITY_RISK",
            "level": "INFO",
            "dimension": "POSITION",
            "title": "相对稳态",
            "description": "当前风险结构相对友好，但需警惕'由于长期不波动而导致的警觉性下降'。"
        }
        
        # D-state 细化
        if dd_state == "D2":
            base_flag["description"] += " 结构中性，保持观察。"
        elif dd_state in ["D0", "D1"]:
            base_flag["description"] += " 结构稳定，是较为安全的环境。"
        
        flags.append(base_flag)
    
    return flags
