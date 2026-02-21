# core/ai_capex_risk_engine.py

from typing import Dict, Any, Tuple, List
import math
from core.config_loader import load_ai_capex_rules

def should_run_ai_capex_risk(
    asset_meta: Dict[str, Any],
    metrics: Dict[str, float],
    rules: Dict[str, Any] | None = None,
) -> Tuple[bool, str]:
    """
    判断是否对该资产 / 报告期运行 AI_CapEX_Risk 模块。
    返回 (should_run, reason_code)
    """
    if rules is None:
        rules = load_ai_capex_rules()
    ar = rules["activation"]

    sector = asset_meta.get("sector_name")           # 如 "Information Technology"
    industry = asset_meta.get("industry_name")       # 如 "Semiconductors"
    tags = set(asset_meta.get("tags", []))           # 如 ["AI_INFRA_CORE", "US_LARGE_CAP"]

    # 1) 禁用 tag：一票否决
    if tags & set(ar.get("disable_if_tags_any", [])):
        return False, "disabled_by_tag"

    # 2) 强制启用 tag
    if tags & set(ar.get("enable_if_tags_any", [])):
        return True, "ok_force_enabled_by_tag"

    # 3) 行业黑名单
    if industry in set(ar.get("industry_blacklist", [])):
        return False, "industry_blacklisted"

    # 4) 行业白名单校验
    if sector not in set(ar.get("sector_whitelist", [])):
        return False, "sector_not_whitelisted"

    # 5) 必须字段完整性检查
    for field in ar.get("required_fields", []):
        if metrics.get(field) is None or math.isnan(metrics.get(field, 0)):
            return False, f"missing_field:{field}"

    # 6) 数值门槛判断
    capex_6m = metrics.get("capex_cash_additions_6m") or 0.0
    revenue_ttm = metrics.get("revenue_ttm") or 0.0
    total_assets = metrics.get("total_assets") or 0.0

    if revenue_ttm <= 0 or total_assets <= 0:
        return False, "bad_base_values"

    capex_intensity = (capex_6m * 2.0) / revenue_ttm
    if capex_intensity < ar.get("min_capex_to_revenue", 0.05):
        return False, "capex_intensity_too_low"

    # 7) AI 数据中心承诺判定（有数据才判断）
    ai_commit = metrics.get("leases_not_commenced_datacenter")
    if ai_commit is not None and not math.isnan(ai_commit):
        ai_commit_ratio = ai_commit / total_assets
        if ai_commit_ratio < ar.get("min_ai_commit_to_assets", 0.01):
            return False, "ai_commitment_not_material"

    return True, "ok"

def run_ai_capex_risk(metrics: Dict[str, float], rules: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """
    运行 AI CapEx 风险评估模型。
    输入 metrics 包含所有原始财务字段。
    """
    if rules is None:
        rules = load_ai_capex_rules()
    
    thresholds = rules.get("thresholds", {})
    buckets_cfg = rules.get("buckets", {})

    # --- 单位归一化逻辑 ---
    # 规则：如果 revenue_ttm 或 total_assets 超过 1,000,000,000，判定为“元/美元”绝对值
    # 我们将其缩放到“百万”级别，以匹配人工输入的 capex_6m (通常为 $49,270M 这种形式)
    def normalize(val: float) -> float:
        if val > 1_000_000_000:
             return val / 1_000_000.0
        return val

    revenue_ttm = normalize(metrics.get("revenue_ttm") or 1.0)
    operating_income_ttm = normalize(metrics.get("operating_income_ttm") or 1.0)
    total_assets = normalize(metrics.get("total_assets") or 1.0)
    
    capex_6m = metrics.get("capex_cash_additions_6m") or 0
    
    # 1) 衍生指标计算
    # 辅助计算 TTM 估计值 (基于半年报外推)
    capex_ttm_approx = capex_6m * 2.0
    
    # 计算强度 (TTM CapEx / TTM Revenue)
    capex_intensity = capex_ttm_approx / revenue_ttm
    
    # 折旧拖累 (Annual PPE Depreciation / Annual Operating Income)
    # 反映了由于大规模基建投入产生的后续折旧对营业利润的蚕食程度
    depreciation_ppe_6m = metrics.get("depreciation_ppe_implied_6m") or ((metrics.get("depreciation_total_6m") or 0) - (metrics.get("amortization_intangibles_6m") or 0))
    depreciation_ppe_ttm_approx = (depreciation_ppe_6m or 0) * 2.0
    depreciation_drag = depreciation_ppe_ttm_approx / operating_income_ttm if operating_income_ttm > 0 else 1.0

    # 租赁相关 (Finance Lease + Operating Lease)
    lease_additions_6m = (metrics.get("lease_capex_finance_additions_6m") or 0) + (metrics.get("lease_capex_operating_additions_6m") or 0)
    lease_capex_share = lease_additions_6m / (capex_6m + lease_additions_6m) if (capex_6m + lease_additions_6m) > 0 else 0
    
    # 表外承诺相关 (Data Center Leases Not Yet Commenced)
    ai_commit = metrics.get("leases_not_commenced_datacenter") or 0
    off_balance_commitment = ai_commit / total_assets
    
    # 对 OpenAI 等战略投资
    strategic_invest = metrics.get("strategic_ai_investment_commitment_total") or 0

    # 2) 打分/定级机理
    def get_bucket(val: float, cfg: Dict[str, float]) -> str:
        if val >= cfg.get("high_gte", 1.0): return "HIGH"
        if val >= cfg.get("medium_gte", 0.5): return "MEDIUM"
        return "LOW"

    scores = {
        "capex_intensity_bucket": get_bucket(capex_intensity, thresholds.get("capex_intensity", {})),
        "depreciation_drag_bucket": get_bucket(depreciation_drag, thresholds.get("depreciation_drag", {})),
        "off_balance_commitment_bucket": get_bucket(off_balance_commitment, thresholds.get("off_balance_commitment", {})),
        "lease_capex_share_bucket": get_bucket(lease_capex_share, thresholds.get("lease_capex_share", {})),
    }

    # 3) 综合风险计算 (0~1)
    # 权重：capex(0.3) + depreciation(0.2) + commitment(0.3) + lease_share(0.2)
    risk_score = (
        (0.3 if scores["capex_intensity_bucket"] == "HIGH" else 0.15 if scores["capex_intensity_bucket"] == "MEDIUM" else 0.05) * 0.3 +
        (0.3 if scores["depreciation_drag_bucket"] == "HIGH" else 0.15 if scores["depreciation_drag_bucket"] == "MEDIUM" else 0.05) * 0.2 +
        (0.3 if scores["off_balance_commitment_bucket"] == "HIGH" else 0.15 if scores["off_balance_commitment_bucket"] == "MEDIUM" else 0.05) * 0.3 +
        (0.3 if scores["lease_capex_share_bucket"] == "HIGH" else 0.15 if scores["lease_capex_share_bucket"] == "MEDIUM" else 0.05) * 0.2
    ) / 0.3 # 归一化近似
    
    risk_score = min(0.99, max(0.01, risk_score))
    
    if risk_score >= 0.7: overall_level = "HIGH"
    elif risk_score >= 0.4: overall_level = "MEDIUM"
    else: overall_level = "LOW"

    # 4) 结果封装
    badge_cfg = buckets_cfg.get("overall_risk", {}).get(overall_level, {"label_zh": "AI 投入关注", "tone": "info"})
    
    return {
        "enabled": True,
        "metrics_derived": {
            "capex_intensity": capex_intensity,
            "depreciation_drag": depreciation_drag,
            "off_balance_commitment": off_balance_commitment,
            "lease_capex_share": lease_capex_share,
            "capex_ttm_approx": capex_ttm_approx,
            "depreciation_ppe_ttm_approx": depreciation_ppe_ttm_approx
        },
        "scoring": {
            **scores,
            "overall_ai_capex_risk_level": overall_level,
            "overall_ai_capex_risk_score": round(risk_score, 2)
        },
        "ui": {
            "headline_badge": {
                "label_zh": badge_cfg["label_zh"],
                "tone": badge_cfg["tone"]
            },
            "key_numbers": [
                {"label_zh": "年化 CapEx 强度", "value": f"{capex_intensity:.1%}"},
                {"label_zh": "表外基建承诺/资产", "value": f"{off_balance_commitment:.1%}"},
                {"label_zh": "未来 AI 战略投资", "value": strategic_invest, "unit": "million"}
            ],
            "summary_zh": f"AI 基础设施投资风险等级为 {overall_level}。当前年化资本开支强度为 {capex_intensity:.1%}，"
                          f"表外数据中心租赁承诺占比为 {off_balance_commitment:.1%}。"
        }
    }
