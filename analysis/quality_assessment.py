from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
from dataclasses import dataclass, field
from datetime import datetime

# --- Helpers ---
def _get_num(f: Dict[str, Any], *keys: str) -> Optional[float]:
    for k in keys:
        v = f.get(k)
        if v is None: continue
        try:
            return float(v)
        except (TypeError, ValueError):
            continue
    return None

def _get_str(f: Dict[str, Any], *keys: str) -> Optional[str]:
    for k in keys:
        v = f.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None

# --- Evaluators ---

class BaseQualityEvaluator:
    """Base class for quality assessment logic."""
    def __init__(self, f: Dict[str, Any]):
        self.f = f
        self.notes_all: List[str] = []

    def log(self, flag: str, note: str):
        self.notes_all.append(f"{flag}: {note}")

    def evaluate_all(self) -> Dict[str, Any]:
        flags = {
            "revenue_stability_flag": self.revenue_stability_flag(),
            "cyclicality_flag": self.cyclicality_flag(),
            "moat_proxy_flag": self.moat_proxy_flag(),
            "balance_sheet_flag": self.balance_sheet_flag(),
            "cashflow_coverage_flag": self.cashflow_coverage_flag(),
            "leverage_risk_flag": self.leverage_risk_flag(),
            "payout_consistency_flag": self.payout_consistency_flag(),
            "dilution_risk_flag": self.dilution_risk_flag(),
            "regulatory_dependence_flag": self.regulatory_dependence_flag(),
        }
        level, summary = self.aggregate_level(flags)
        
        # Identify Template Name
        template_name = "General"
        if isinstance(self, BankQualityEvaluator):
            template_name = "Banks"

        return {
            **flags,
            "quality_template_name": template_name,
            "quality_buffer_level": level,
            "quality_summary": summary,
            "quality_notes": self.notes_all
        }

    def aggregate_level(self, flags: Dict[str, str]) -> Tuple[str, str]:
        # Default aggregation (will be overridden by children)
        return "MODERATE", "Default aggregation"

class GeneralQualityEvaluator(BaseQualityEvaluator):
    """通用模板 (默认 / 平台股同用)"""
    
    def revenue_stability_flag(self) -> str:
        # 1.1 收入稳定性 - STRONG / MID / WEAK
        rev_ttm = _get_num(self.f, "revenue_ttm")
        hist = self.f.get("revenue_history", [])
        
        if not rev_ttm or rev_ttm <= 0 or not isinstance(hist, list) or len(hist) < 4:
            self.log("revenue_stability", "Data insufficient or TTM <= 0")
            return "WEAK"
        
        revs = np.array([float(x) for x in hist if x is not None], dtype=float)
        if len(revs) < 4: return "WEAK"
        
        # YoY check (last 8 quarters or all available)
        yoy = (revs[1:] / np.maximum(revs[:-1], 1e-9)) - 1.0
        pos_yoy_ratio = np.mean(yoy > 0)
        vol = float(np.std(revs) / np.mean(revs)) if np.mean(revs) > 0 else 1.0
        
        if pos_yoy_ratio >= 0.75 and vol < 0.25:
            return "STRONG"
        if vol < 0.5:
            return "MID"
        return "WEAK"

    def cyclicality_flag(self) -> str:
        # 1.2 周期敏感度 - LOW / MID / HIGH
        sector = (_get_str(self.f, "sector", "industry") or "").lower()
        if not sector: return "MID"
        
        low_sectors = ["staples", "healthcare", "utilities", "telecom", "运营", "保健", "必选"]
        high_sectors = ["energy", "materials", "industrials", "discretionary", "real estate", "能源", "材料", "工业", "房地产", "周期"]
        
        if any(x in sector for x in low_sectors): return "LOW"
        if any(x in sector for x in high_sectors): return "HIGH"
        return "MID"

    def moat_proxy_flag(self) -> str:
        # 1.3 竞争壁垒代理 - STRONG / MID / WEAK
        margin = _get_num(self.f, "net_margin", "profit_margin") # 0..1
        roe = _get_num(self.f, "roe") # 0..1
        
        # Fallback if margin missing but raw data exists
        if margin is None:
            ni = _get_num(self.f, "net_income_ttm")
            rev = _get_num(self.f, "revenue_ttm")
            if ni and rev and rev > 0: margin = ni / rev

        if margin is None: return "WEAK"
        
        if margin >= 0.20: return "STRONG"
        if margin >= 0.10: return "MID"
        return "WEAK"

    def balance_sheet_flag(self) -> str:
        # 2.1 资产负债表弹性 - STRONG / MID / WEAK
        pb = _get_num(self.f, "pb_ttm", "pb")
        de = _get_num(self.f, "debt_to_equity") # 0..1
        
        if pb is None or de is None: return "WEAK"
        
        if pb <= 3 and de <= 0.8: return "STRONG"
        if pb <= 5 and de <= 1.5: return "MID"
        return "WEAK"

    def cashflow_coverage_flag(self) -> str:
        # 2.2 现金流覆盖 - STRONG / MID / WEAK
        ni = _get_num(self.f, "net_income_ttm")
        div = _get_num(self.f, "dividend_ttm", "dividend_yield")
        
        if ni is None or ni <= 0: return "WEAK"
        if div and div > 0: return "STRONG"
        return "MID"

    def leverage_risk_flag(self) -> str:
        # 2.3 杠杆风险 - LOW / MID / HIGH
        de = _get_num(self.f, "debt_to_equity")
        if de is None: return "LOW" # Assuming light asset if missing
        
        if de <= 0.5: return "LOW"
        if de <= 1.0: return "MID"
        return "HIGH"

    def payout_consistency_flag(self) -> str:
        # 3.1 分红 / 回购一致性 - POSITIVE / NEUTRAL / NEGATIVE
        dy = _get_num(self.f, "dividend_yield_ttm", "dividend_yield") or 0.0
        by = _get_num(self.f, "buyback_yield_ttm") or 0.0
        
        if dy >= 0.01 or by >= 0.02: return "POSITIVE"
        if dy > 0 or by > 0: return "NEUTRAL"
        return "NEGATIVE"

    def dilution_risk_flag(self) -> str:
        # 3.2 稀释风险 - LOW / HIGH
        by = _get_num(self.f, "buyback_yield_ttm") or 0.0
        shares_delta = _get_num(self.f, "shares_yoy") or 0.0
        
        if by > 0 or shares_delta <= 0: return "LOW"
        return "HIGH"

    def regulatory_dependence_flag(self) -> str:
        # 3.3 政策/监管依赖度 - LOW / MID / HIGH
        sector = (_get_str(self.f, "sector", "industry") or "").lower()
        high = ["healthcare", "utilities", "banks", "telecom", "消费", "医药"]
        mid = ["tech", "platform", "comm", "finance"]
        
        if any(x in sector for x in high): return "HIGH"
        if any(x in sector for x in mid): return "MID"
        return "LOW"

    def aggregate_level(self, flags: Dict[str, str]) -> Tuple[str, str]:
        # 4. 汇总：quality_buffer_level
        strong_bs = flags["balance_sheet_flag"] == "STRONG"
        strong_cf = flags["cashflow_coverage_flag"] == "STRONG"
        low_lev = flags["leverage_risk_flag"] == "LOW"
        
        if strong_bs and strong_cf and low_lev:
            return "STRONG", "资产负债表与现金流极佳，具备核心财务安全垫。"
        
        # Count mid-tier items
        mids = sum(1 for v in flags.values() if v in ["MID", "NEUTRAL", "POSITIVE"])
        if mids >= 3:
            return "MODERATE", "整体质量中规中矩，具备一定的抗风险能力。"
            
        return "WEAK", "关键财务指标较弱或缺失，质量缓冲空间有限。"

class BankQualityEvaluator(GeneralQualityEvaluator):
    """银行模板 (Bank Quality Profile)"""
    
    def revenue_stability_flag(self) -> str:
        # 1.1 核心营收稳定性 (NII + Fees)
        nii = _get_num(self.f, "net_interest_income")
        fees = _get_num(self.f, "net_fee_income")
        
        if nii is None or fees is None:
            return super().revenue_stability_flag()
            
        core_rev = nii + fees
        if core_rev <= 0: return "WEAK"
        
        # Simplified trend (using TTM vs prev if history missing)
        return "MID" # Default to MID if deep history not present in this pass

    def moat_proxy_flag(self) -> str:
        # 1.3 竞争壁垒 - roe_ttm ≥ 12%
        roe = _get_num(self.f, "roe")
        if roe is None: return "WEAK"
        if roe >= 0.12: return "STRONG"
        if roe >= 0.08: return "MID"
        return "WEAK"

    def balance_sheet_flag(self) -> str:
        # 2.1 资本充足率 - core_tier1_capital_ratio ≥ 12%
        # Note: Database stores as percentage (12.71 = 12.71%), not decimal (0.1271)
        cet1 = _get_num(self.f, "core_tier1_capital_ratio", "core_tier1_ratio")
        if cet1 is None: return "WEAK"
        
        # Normalize: if value is small (< 2), assume decimal format; otherwise percentage
        if cet1 < 2.0:
            # Decimal format: 0.1271 = 12.71%
            if cet1 >= 0.12: return "STRONG"
            if cet1 >= 0.10: return "MID"
        else:
            # Percentage format: 12.71 = 12.71%
            if cet1 >= 12.0: return "STRONG"
            if cet1 >= 10.0: return "MID"
        
        return "WEAK"

    def leverage_risk_flag(self) -> str:
        # 2.3 信贷成本 & 拨备纪律
        prov = _get_num(self.f, "provision_expense")
        loans = _get_num(self.f, "total_loans")
        
        if prov is None or loans is None or loans == 0:
            return "MID"
            
        credit_cost = prov / loans
        # Typical range 0.3% - 1.5%
        if 0.003 <= credit_cost <= 0.015: return "LOW"
        return "MID"

    def payout_consistency_flag(self) -> str:
        # 3.1 银行级分红
        dy = _get_num(self.f, "dividend_yield_ttm", "dividend_yield") or 0.0
        if dy >= 0.03: return "POSITIVE"
        if dy >= 0.01: return "NEUTRAL"
        return "NEGATIVE"

    def regulatory_dependence_flag(self) -> str:
        return "HIGH" # All banks are HIGH

    def aggregate_level(self, flags: Dict[str, str]) -> Tuple[str, str]:
        # 4. 银行汇总逻辑
        bst_strong = flags["balance_sheet_flag"] == "STRONG"
        lev_low = flags["leverage_risk_flag"] == "LOW"
        cf_nok = flags["cashflow_coverage_flag"] == "WEAK"
        
        if bst_strong and lev_low and not cf_nok:
            return "STRONG", "资本充足且拨备纪律良好，银行底层资产稳健。"
            
        if flags["balance_sheet_flag"] == "WEAK" or flags["leverage_risk_flag"] == "HIGH" or cf_nok:
            return "WEAK", "核心资本或信贷质量存在明显短板，需警惕尾部风险。"
            
        return "MODERATE", "银行各项监管指标处于行业平均水平，质量缓冲适中。"


# --- Dataclasses ---

@dataclass
class QualitySnapshot:
    quality_template_name: str
    revenue_stability_flag: str
    cyclicality_flag: str
    moat_proxy_flag: str
    balance_sheet_flag: str
    cashflow_coverage_flag: str
    leverage_risk_flag: str
    payout_consistency_flag: str
    dilution_risk_flag: str
    regulatory_dependence_flag: str
    quality_buffer_level: str
    quality_summary: str
    
    # Existing compatibility fields
    dividend_safety_level: Optional[str] = None
    dividend_safety_label_zh: Optional[str] = None
    dividend_safety_score: Optional[float] = None
    earnings_state_code: Optional[str] = None
    earnings_state_label_zh: Optional[str] = None
    earnings_state_desc_zh: Optional[str] = None
    
    notes: Dict[str, Any] = field(default_factory=dict)

# --- Entry Points ---

def build_quality_snapshot(
    asset_id: str,
    fundamentals: Any,
    bank_metrics: Optional[Any] = None,
    risk_context: Optional[Dict[str, Any]] = None,
    dividend_info: Optional[Any] = None,
    earnings_info: Optional[Any] = None
) -> QualitySnapshot:
    
    # 1. Map object to dict
    f_dict = {}
    if hasattr(fundamentals, '__dict__'):
        f_dict = vars(fundamentals).copy()
    
    # 2. Field Mapping for compatibility
    # Map net_profit_ttm to net_income_ttm (used in evaluators)
    if 'net_profit_ttm' in f_dict and 'net_income_ttm' not in f_dict:
        f_dict['net_income_ttm'] = f_dict['net_profit_ttm']
    
    # Map pb_ratio to pb_ttm
    if 'pb_ratio' in f_dict and 'pb_ttm' not in f_dict:
        f_dict['pb_ttm'] = f_dict['pb_ratio']

    # Inject bank metrics if present
    if bank_metrics and hasattr(bank_metrics, '__dict__'):
        f_dict.update(vars(bank_metrics))
        # Ensure it has role 'Bank' if bank_metrics is present
        if 'industry' not in f_dict or f_dict['industry'] != 'Bank':
            f_dict['industry'] = 'Bank'

    # 2. Template Selection
    industry = (_get_str(f_dict, "industry", "sector") or "").lower()
    is_bank = "bank" in industry or "银行" in industry
    
    if is_bank:
        evaluator = BankQualityEvaluator(f_dict)
    else:
        evaluator = GeneralQualityEvaluator(f_dict)

    # 3. Evaluate
    res = evaluator.evaluate_all()
    
    # 4. Wrap for return
    final_notes = {"details": res["quality_notes"]}
    if dividend_info and hasattr(dividend_info, 'notes_zh'):
        final_notes["dividend_notes"] = dividend_info.notes_zh
        
    return QualitySnapshot(
        **{k: v for k, v in res.items() if k != "quality_notes"},
        dividend_safety_level=getattr(dividend_info, 'level', None),
        dividend_safety_label_zh=getattr(dividend_info, 'label_zh', None),
        dividend_safety_score=getattr(dividend_info, 'score', None),
        earnings_state_code=getattr(earnings_info, 'code', None),
        earnings_state_label_zh=getattr(earnings_info, 'label_zh', None),
        earnings_state_desc_zh=getattr(earnings_info, 'desc_zh', None),
        notes=final_notes
    )

def build_quality_flags(fundamentals: Dict[str, Any]) -> Dict[str, Any]:
    """Legacy entry point for generic dict-based calls."""
    industry = (_get_str(fundamentals, "industry", "sector") or "").lower()
    is_bank = "bank" in industry or "银行" in industry
    evaluator = BankQualityEvaluator(fundamentals) if is_bank else GeneralQualityEvaluator(fundamentals)
    return evaluator.evaluate_all()
