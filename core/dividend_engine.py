from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from core.config_loader import load_vera_rules

@dataclass
class DividendSafetyInfo:
    level: str            # "STRONG" / "MEDIUM" / "WEAK"
    label_zh: str
    score: float
    notes_zh: List[str]   # 若干条中文解释文案

@dataclass
class DividendFacts:
    asset_id: str
    dividends_ttm: Optional[float]
    net_income_ttm: Optional[float]
    dps_5y_mean: Optional[float]
    dps_5y_std: Optional[float]
    cut_years_10y: Optional[int]
    dividend_recovery_progress: Optional[float]


def _safe_div(num: Optional[float], den: Optional[float]) -> Optional[float]:
    # 简单防御性除法，0 或 None 返回 None
    if num is None or den is None or den == 0:
        return None
    return num / den

def _score_from_range(
    value: float, 
    strong_threshold: float, 
    weak_threshold: float, 
    direction: str = "down"
) -> float:
    """
    将 value 映射到 0.0 - 1.0 的分数。
    
    direction="down": 值越小越好 (e.g. payout ratio)
      - value <= strong_threshold -> 1.0
      - value >= weak_threshold -> 0.0
      - 中间线性插值
      
    direction="up": 值越大越好 (e.g. recovery progress)
      - value >= strong_threshold -> 1.0
      - value <= weak_threshold -> 0.0
    """
    if direction == "down":
        if value <= strong_threshold:
            return 1.0
        if value >= weak_threshold:
            return 0.0
        # Linear interpolation
        # range = weak - strong
        # relative = value - strong
        # score = 1 - (relative / range)
        return 1.0 - (value - strong_threshold) / (weak_threshold - strong_threshold)
    else: # direction == "up"
        if value >= strong_threshold:
            return 1.0
        if value <= weak_threshold:
            return 0.0
        return (value - weak_threshold) / (strong_threshold - weak_threshold)


def evaluate_dividend_safety(
    facts: DividendFacts,
    rules: Dict[str, Any] | None = None
) -> Optional[DividendSafetyInfo]:
    """
    基于 DividendFacts 和 vera_rules.yaml 的 dividend_safety 配置，
    计算分红安全等级。

    返回:
    - DividendSafetyInfo, 若关键字段严重缺失，可返回 None，由上游决定是否显示该模块。
    """
    if rules is None:
        rules = load_vera_rules()
    
    # 防御性检查：如果没有 dividend_safety 配置，直接返回 None
    drules = rules.get("dividend_safety")
    if not drules:
        return None

    notes: List[str] = []

    # 1) 计算指标
    payout = _safe_div(facts.dividends_ttm, facts.net_income_ttm)
    
    # Volatility Check
    if facts.dps_5y_std is not None and facts.dps_5y_mean is not None and facts.dps_5y_mean != 0:
        vol = facts.dps_5y_std / facts.dps_5y_mean
    else:
        vol = None
        
    cut_years = facts.cut_years_10y
    rec = facts.dividend_recovery_progress

    # 若没有任何关键数据，无法评估
    if payout is None and vol is None and cut_years is None and rec is None:
        return None

    # 2) 映射分数
    # Payout Ratio
    if payout is not None:
        # 如果 payout 为负 (亏损派息)，视为极度危险 -> 0分，且 payout ratio 本身没有意义
        if facts.net_income_ttm is not None and facts.net_income_ttm < 0:
             score_payout = 0.0
             notes.append("当前亏损仍派息，不可持续性风险极高")
        else:
            # 正常盈利情况
            cfg = drules["payout_ratio_ttm"]
            score_payout = _score_from_range(payout, cfg["strong_max"], cfg["weak_min"], "down")
            if payout >= cfg["weak_min"]:
                if payout > 1.0:
                    notes.append(f"派息率 {payout*100:.0f}% 远超盈利，如无特殊现金流支持将不可持续")
                else:
                    notes.append(f"派息率 {payout*100:.0f}% 偏高，只有极低资本开支企业可维持")
    else:
        score_payout = 0.5 # Default neutral if missing

    # Volatility
    if vol is not None:
        cfg = drules["dps_volatility"]
        score_vol = _score_from_range(vol, cfg["strong_max"], cfg["weak_min"], "down")
        if vol >= cfg["weak_min"]:
            notes.append(f"历史股息波动极大 (CV={vol:.2f})，缺乏稳定性")
    else:
        score_vol = 0.5

    # Cut Years
    if cut_years is not None:
        cfg = drules["cut_years"]
        score_cut = _score_from_range(cut_years, cfg["strong_max"], cfg["weak_min"], "down")
        if cut_years >= cfg["weak_min"]:
            notes.append(f"过去10年有 {cut_years} 年减派或停派，分红意愿或能力不稳定")
    else:
        score_cut = 0.5
        
    # Recovery Progress
    # 特殊逻辑：对于没有停派历史的，recovery_progress 可能是 1.0 (Full) or None?
    # 假设上游对于没有危机的公司给 1.0。如果为 None，可能是数据不足。
    if rec is not None:
        cfg = drules["recovery_progress"]
        # 注意：Recovery 是越高越好，但配置里用了 early_max (0.4), mid_max (0.8), full_min (0.8)
        # 这里的命名稍微有点混淆，我们用数值区间判断。
        # 0.0 --[early]--> 0.4 --[mid]--> 0.8 --[full]--> 1.0
        # 我们可以认为 > 0.8 就是 Strong (1.0分), < 0.4 就是 Weak (0.0分)
        # 用 "up" direction 映射
        score_rec = _score_from_range(rec, cfg["early_max"], cfg["full_min"], "up")
        
        if rec < cfg["early_max"]:
            notes.append(f"分红处于恢复早期 ({rec*100:.0f}%)，距离常态仍有较大差距")
        elif rec < cfg["full_min"]:
            notes.append(f"分红处于恢复中段 ({rec*100:.0f}%)，逐步接近常态")
    else:
        score_rec = 1.0 # 默认没问题

    # 3) 加权汇总
    weights = drules["scoring"]
    # Normalize weights? Assuming they sum to 1.0 in config, but let's be safe.
    w_p = weights.get("payout_weight", 0.4)
    w_v = weights.get("stability_weight", 0.3)
    w_c = weights.get("cut_weight", 0.2)
    w_r = weights.get("recovery_weight", 0.1)
    
    total_weight = w_p + w_v + w_c + w_r
    if total_weight == 0: total_weight = 1.0
    
    total_score = (score_payout * w_p + score_vol * w_v + score_cut * w_c + score_rec * w_r) / total_weight

    # 4) 根据 bands 选择等级
    bands = drules["bands"]
    # Sort bands by min_score descending to find the first match
    # Assuming bands are distinct ranges, usually configured as:
    # STRONG (>=0.75), MEDIUM (>=0.4), WEAK (>=0.0)
    # We iterate and pick the first one that total_score satisfies.
    
    # 按照 min_score 降序排列，以便命中最高的门槛
    sorted_bands = sorted(bands, key=lambda x: x["min_score"], reverse=True)
    
    selected_band = sorted_bands[-1] # Default to lowest
    for band in sorted_bands:
        if total_score >= band["min_score"]:
            selected_band = band
            break
            
    # 如果 notes 为空，补一句通用解释
    if not notes:
        notes.append(selected_band.get("desc_zh", ""))

    return DividendSafetyInfo(
        level=selected_band["key"],
        label_zh=selected_band.get("label_zh", selected_band["key"]),
        score=total_score,
        notes_zh=notes
    )
