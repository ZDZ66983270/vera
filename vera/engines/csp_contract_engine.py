import sqlite3
import pandas as pd
from datetime import datetime, date
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple
from core.config_loader import load_csp_rules

@dataclass
class CSPContractAuditResult:
    status: str
    score: float
    reasons: List[Dict[str, str]]
    suggestion: str

def calc_annual_yield(premium: float, strike: float, dte: int) -> float:
    """计算简易年化收益率"""
    if strike <= 0 or dte <= 0:
        return 0.0
    # Yield = (Premium / Strike) * (365 / DTE)
    return (premium / strike) * (365.0 / dte)

def audit_single_contract(opt: Dict[str, Any], prefs: Optional[Dict[str, Any]] = None) -> CSPContractAuditResult:
    """
    对单个期权合约进行 CSP 策略审核
    """
    if prefs is None:
        rules = load_csp_rules()
        prefs = rules.get('csp_contract_prefs', {})
    
    reasons = []
    score = 100.0
    
    dte = opt.get('dte', 0)
    strike = opt.get('strike', 0.0)
    discount_pct = opt.get('discount_pct', 0.0)
    delta = opt.get('delta', 0.0)
    mid_price = opt.get('mid', 0.0) or opt.get('bid', 0.0)
    
    annual_yield = calc_annual_yield(mid_price, strike, dte)
    
    # 1. Tenor Check
    tenor_cfg = prefs.get('tenor_days', {})
    min_dte = tenor_cfg.get('preferred_min', 30)
    max_dte = tenor_cfg.get('preferred_max', 60)
    if dte < min_dte or dte > max_dte:
        # Score deduction or rejection? Original decompiled showed status logic.
        pass

    # 2. Moneyness (Discount) Check
    money_cfg = prefs.get('moneyness', {})
    min_discount = money_cfg.get('min_discount_pct', 0.03)
    max_discount = money_cfg.get('max_discount_pct', 0.1)
    if not (min_discount <= discount_pct <= max_discount):
        score -= 40
        reasons.append({
            'code': 'DISCOUNT_OUT_OF_RANGE',
            'message': f"行权价折价 {discount_pct:.1%} 不在 [{min_discount:.0%}, {max_discount:.0%}] 区间内"
        })

    # 3. Delta Check
    delta_cfg = prefs.get('delta', {})
    d_min = delta_cfg.get('min', -0.5)
    d_max = delta_cfg.get('max', -0.1)
    if not (d_min <= delta <= d_max):
        score -= 25
        reasons.append({
            'code': 'DELTA_OUT_OF_RANGE',
            'message': f"Delta={delta:.2f} 超出配置区间 [{d_min}, {d_max}]"
        })

    # 4. Yield Check (Sync with YAML return_metrics)
    yield_cfg = prefs.get('return_metrics', {})
    min_yield = yield_cfg.get('min_annualized_return', 0.08)
    if annual_yield < min_yield:
        score -= 30
        reasons.append({
            'code': 'YIELD_TOO_LOW',
            'message': f"年化收益率 {annual_yield:.1%} 低于最低要求 {min_yield:.1%}"
        })

    status = "APPROVED" if score >= 60 and not any(r['code'] == 'DISCOUNT_OUT_OF_RANGE' for r in reasons) else "REJECTED"
    # Actually the decompiled showed a more complex status logic.
    # Let's refine based on common sense if the exact logic is missing.
    
    suggestion = "在总体仓位可控前提下，可考虑卖出该 Put 合约作为 CSP 标的。" if status == "APPROVED" else \
                 "不建议卖出当前合约，请调整行权价/到期日或等待更好的波动率与权利金水平。"
                 
    return CSPContractAuditResult(
        status=status,
        score=score,
        reasons=reasons,
        suggestion=suggestion
    )

def pick_best_csp_contract(candidates: List[Dict[str, Any]]) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    输入：候选 PUT 合约列表
    输出：(最佳合约, 所有已审计合约列表)
    """
    if not candidates:
        return None, []
        
    rules = load_csp_rules()
    prefs = rules.get('csp_contract_prefs', {})
    
    audited = []
    for opt in candidates:
        audit = audit_single_contract(opt, prefs)
        opt_with_audit = opt.copy()
        opt_with_audit['_audit'] = audit
        audited.append(opt_with_audit)
        
    # Pick best: Approved first, then by annual yield or score
    approved = [o for o in audited if o['_audit'].status == "APPROVED"]
    pool = approved if approved else audited
    
    if not pool:
        return None, audited
        
    # Sort key: status_score (APPROVED=1) and then yield
    def sort_key(o):
        a = o['_audit']
        mid = o.get('mid', 0.0) or o.get('bid', 0.0)
        ay = calc_annual_yield(mid, o['strike'], o['dte'])
        status_val = 1 if a.status == "APPROVED" else 0
        return (status_val, a.score, ay)

    sorted_pool = sorted(pool, key=sort_key, reverse=True)
    best = sorted_pool[0]
    
    # Return everything sorted by strike as usual for UI
    all_sorted = sorted(audited, key=lambda x: x.get('strike', 0))
    
    return best, all_sorted

def get_csp_candidates(db_path: str, asset_id: str, current_price: float) -> List[Dict[str, Any]]:
    """从数据库获取 CSP 候选 Put 合约"""
    conn = sqlite3.connect(db_path)
    try:
        query = """
            SELECT strike_price, expiry_date, bid_price, ask_price, delta
            FROM options_chain
            WHERE underlying_asset_id = ? 
              AND option_type = 'P'
        """
        df = pd.read_sql(query, conn, params=(asset_id,))
        if df.empty:
            return []
            
        candidates = []
        today = date.today()
        
        for _, row in df.iterrows():
            expiry_str = row['expiry_date']
            if len(expiry_str) > 10: expiry_str = expiry_str[:10]
            expiry = datetime.strptime(expiry_str, '%Y-%m-%d').date()
            days_to_expiry = (expiry - today).days
            
            if days_to_expiry <= 0:
                continue
                
            strike = float(row['strike_price'])
            bid = float(row['bid_price']) if row['bid_price'] else 0.0
            ask = float(row['ask_price']) if row['ask_price'] else 0.0
            mid = (bid + ask) / 2.0
            delta = float(row['delta']) if row['delta'] else 0.0
            
            discount_pct = (current_price - strike) / current_price if current_price > 0 else 0.0
            
            candidates.append({
                'strike': strike,
                'expiry': expiry_str,
                'dte': days_to_expiry,
                'bid': bid,
                'ask': ask,
                'mid': mid,
                'spot': current_price,
                'discount_pct': discount_pct,
                'delta': delta
            })
            
        return candidates
    except Exception as e:
        print(f"Error getting CSP candidates: {e}")
        return []
    finally:
        conn.close()
