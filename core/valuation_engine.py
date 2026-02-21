from dataclasses import dataclass
from typing import Dict, Any, Sequence
from core.config_loader import load_vera_rules

@dataclass
class ValuationStatusInfo:
    key: str
    label_zh: str
    label_en: str
    bucket: str        # "CHEAP" / "NEUTRAL" / "EXPENSIVE"
    color: str | None = None

def compute_valuation_status(
    vera_pe_ttm: float | None,
    pe_history: Sequence[float] | None,
    rules: Dict[str, Any] | None = None,
) -> ValuationStatusInfo:
    """
    统一出口：
    - 没有当前 PE → NO_PE
    - 历史样本不足 → INSUFFICIENT_HISTORY
    - 其余情况 → 按分位数映射估值状态
    """
    if rules is None:
        rules = load_vera_rules()
    vrules = rules["valuation"]
    special = vrules.get("special_states", {})
    min_pts = vrules.get("min_history_points", 0)

    # 1) 没有当前 PE
    if vera_pe_ttm is None:
        s = special.get("NO_PE") or {"key": "NO_PE", "label_zh": "估值暂不可用", "label_en": "Valuation N/A", "bucket": "NEUTRAL"}
        return ValuationStatusInfo(
            key=s["key"],
            label_zh=s["label_zh"],
            label_en=s["label_en"],
            bucket=s["bucket"],
            color=None,
        )

    # 2) 历史样本不足
    if not pe_history or len(pe_history) < min_pts:
        s = special.get("INSUFFICIENT_HISTORY") or {"key": "INSUFFICIENT_HISTORY", "label_zh": "历史样本不足", "label_en": "Insufficient history", "bucket": "NEUTRAL"}
        return ValuationStatusInfo(
            key=s["key"],
            label_zh=s["label_zh"],
            label_en=s["label_en"],
            bucket=s["bucket"],
            color=None,
        )

    # 3) 有足够历史：按分位数计算
    pct = _percentile_rank(pe_history, vera_pe_ttm)  # 返回 0–100
    return map_valuation_status_from_pctile(pct, rules)

def _percentile_rank(history: Sequence[float], current: float) -> float:
    if not history: return 50.0 # Should not happen given check above
    count = sum(1 for x in history if x < current)
    return (count / len(history)) * 100.0

def map_valuation_status_from_pctile(
    pct: float,
    rules: Dict[str, Any] | None = None
) -> ValuationStatusInfo:
    """
    根据 VERA_PE TTM 分位数 (0-100) 映射估值状态。
    配置来源：rules["valuation"]["bands"] & rules["valuation"]["buckets"]。
    要求：pct 必须是 0–100 标度。
    """
    if rules is None:
        rules = load_vera_rules()
    vrules = rules["valuation"]
    bands = vrules["bands"]
    buckets = vrules["buckets"]

    matched_band_key = None
    matched_band = None

    for band in bands:
        lo, hi = band["range"]
        # 区间约定：[lo, hi)，最高一档允许 hi==100 且 pct==100 命中
        # Ensure we handle floating point comparison robustly if needed, but usually direct is fine.
        if pct >= lo and (pct < hi or (hi == 100 and pct == 100)):
            matched_band_key = band["key"]
            matched_band = band
            break

    if matched_band_key is None:
        raise ValueError(f"Valuation pctile {pct} not in any band")

    bucket = None
    for bucket_name, cfg in buckets.items():
        if matched_band_key in cfg["bands"]:
            bucket = bucket_name
            break

    if bucket is None:
        raise ValueError(f"Valuation band {matched_band_key} not mapped to any bucket")

    return ValuationStatusInfo(
        key=matched_band_key,
        label_zh=matched_band.get("label_zh", matched_band_key),
        label_en=matched_band.get("label_en", matched_band_key),
        bucket=bucket,
        color=matched_band.get("color"),
    )
