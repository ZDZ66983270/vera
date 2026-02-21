from dataclasses import dataclass
from typing import Literal, Dict, Any
from core.config_loader import load_vera_rules

@dataclass
class QuadrantInfo:
    quadrant: str
    label_zh: str
    label_en: str
    desc_zh: str
    desc_en: str
    color: str | None = None

def compute_position_bin(
    position_pct: float,
    rules: Dict[str, Any] | None = None
) -> Literal["HIGH", "LOW"]:
    """
    Position(10Y) 分位数 → HIGH / LOW
    - 输入 position_pct 必须是 0–100（不是 0–1）
    - 阈值来自 rules["quadrant"]["position_bin"]["high_gte"]
    """
    if rules is None:
        rules = load_vera_rules()
    qrules = rules["quadrant"]
    high_gte = qrules["position_bin"]["high_gte"]
    return "HIGH" if position_pct >= high_gte else "LOW"

def compute_path_bin(
    d_state: str,
    rules: Dict[str, Any] | None = None
) -> Literal["STABLE", "FRAGILE"]:
    """
    D-State → STABLE / FRAGILE
    脆弱状态集合来自 rules["quadrant"]["path_bin"]["fragile_states"]
    """
    if rules is None:
        rules = load_vera_rules()
    fragile = set(rules["quadrant"]["path_bin"]["fragile_states"])
    return "FRAGILE" if d_state in fragile else "STABLE"

def map_quadrant(
    position_bin: str,
    path_bin: str,
    rules: Dict[str, Any] | None = None
) -> QuadrantInfo:
    """
    (position_bin, path_bin) 查表得到 Q1..Q4 及文案
    配置来源：rules["quadrant"]["matrix"]
    """
    if rules is None:
        rules = load_vera_rules()
    matrix = rules["quadrant"]["matrix"]
    for item in matrix:
        if item["position"] == position_bin and item["path"] == path_bin:
            return QuadrantInfo(
                quadrant=item["quadrant"],
                label_zh=item.get("label_zh", item["quadrant"]),
                label_en=item.get("label_en", item["quadrant"]),
                desc_zh=item.get("desc_zh", ""),
                desc_en=item.get("desc_en", ""),
                color=item.get("color"),
            )

    # fallback：未命中任何配置
    return QuadrantInfo(
        quadrant="UNKNOWN",
        label_zh="未知象限",
        label_en="Unknown",
        desc_zh="组合未在配置中定义，请检查 vera_rules.yaml。",
        desc_en="Quadrant not defined in rules.",
        color="#666666",
    )
