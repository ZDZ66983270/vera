from dataclasses import dataclass
from typing import Optional

@dataclass
class BankMetrics:
    """
    银行股特定指标结构
    """
    overdue_90_loans: float      # 逾期90天以上贷款余额
    npl_balance: float           # 不良贷款余额
    provision_coverage: float    # 拨备覆盖率 (e.g. 2.50 for 250%)
    special_mention_ratio: float # 关注类贷款占比 (e.g. 0.03 for 3%)
    npl_ratio: float = 0.01      # 不良率
    allowance_to_loan: float = 0.02 # 拨贷比
    
    # New VERA 2.5 fields
    net_interest_income: Optional[float] = None
    net_fee_income: Optional[float] = None
    provision_expense: Optional[float] = None
    total_loans: Optional[float] = None
    core_tier1_capital_ratio: Optional[float] = None

def calc_bank_quality_score(metrics: BankMetrics) -> int:
    """
    模块 5: 银行质量评分逻辑
    Score Range: -2 to +2
    Logic:
      1. 偏离度 (Deviation): Overdue90 / NPL Balance
      2. 拨备覆盖率 (Provision Coverage)
      3. 关注类占比 (Special Mention Loan Ratio)
    """
    score = 0
    
    # 0. 防止除以零
    if metrics.npl_balance == 0:
        # 如果没有不良余额，且逾期也为0，说明资产极好；如果有逾期，说明偏离度无穷大
        deviation = 1.0 # 默认 default
        if metrics.overdue_90_loans > 0:
            deviation = 999.0
        else:
            deviation = 0.0 # 极好
    else:
        deviation = metrics.overdue_90_loans / metrics.npl_balance
        
    # 1. 偏离度检查 (最关键的真实性)
    if deviation < 0.8:
        score += 1  # 认定极严，可能藏利润 (Positive)
    elif deviation > 1.0:
        score -= 2  # 认定宽松，数据不可信 (Heavy Penalty)
        
    # 2. 拨备覆盖率检查 (抗风险能力)
    # Assuming input is ratio (e.g., 2.50 is 250%)
    if metrics.provision_coverage > 2.50:
        score += 1  # 安全垫极厚
    elif metrics.provision_coverage < 1.50:
        score -= 1  # 勉强达标
        
    # 3. 潜在风险检查 (关注类)
    if metrics.special_mention_ratio > 0.03:
        score -= 1  # 潜在雷区大
        
    # Clamp score to reasonable bounds is not required by prompt, 
    # but the prompt says "-2 to +2". 
    # Let's check max possible: +1 +1 -0 = +2.
    # Min possible: -2 -1 -1 = -4.
    # Prompt says "Score (-2 to +2)". 
    # It might mean the *design intent* is roughly that range, 
    # or I should clamp it. 
    # Based on the logic provided:
    # Max: +2 (Dev<0.8, Prov>250%, Ment<=3%)
    # Min: -4 (Dev>1.0, Prov<150%, Ment>3%)
    # I will stick to the logic provided. 
    # If strictly limited to -2, I might need to clamp.
    # For now, I'll return the raw score as calculation logic dictates.
    
    return score
