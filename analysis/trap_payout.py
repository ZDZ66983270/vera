from analysis.valuation import AssetFundamentals

def detect_value_trap(asset: AssetFundamentals) -> bool:
    """
    模块三 part 1: 价值陷阱识别
    Trigger Conditions (AND):
      1. 股息率 > 5% (看似高息)
      2. 营收/利润 3年复合增长率 < 0 (基本面恶化) -> 只要有一个 < 0 就算
      3. 估值状态 != "Undervalued" (或 PE 仍处高位)
    """
    # Condition 1: High Yield
    cond1 = asset.dividend_yield > 0.05
    
    # Condition 2: Negative Growth
    # Assuming growth is passed as a float, e.g., -0.05 for -5%
    # Checks if EITHER revenue OR profit growth is negative
    # Handle None values gracefully
    cond2 = False
    if asset.revenue_growth_3y is not None and asset.revenue_growth_3y < 0:
        cond2 = True
    if asset.profit_growth_3y is not None and asset.profit_growth_3y < 0:
        cond2 = True
    
    # Condition 3: Not Undervalued
    cond3 = asset.valuation_status != "Undervalued"
    
    base_trap = cond1 and cond2 and cond3
    
    # --- Bank Specific Logic (假净资产陷阱) ---
    if asset.industry == "Bank":
        # 如果是银行，除了通过基本陷阱（尽管银行股息率通常高，可能误判，需结合 negative growth），
        # 还需检查特定的资产质量陷阱。
        # 触发条件 (OR):
        # 1. 偏离度陷阱: 不良偏离度 > 120% (1.2)
        # 2. 拨备裸奔: 拨备覆盖率 < 130% (1.3)
        # 3. 隐性恶化: (暂未实现跨季度对比)
        
        bank_trap = False
        if asset.npl_deviation is not None and asset.npl_deviation > 1.2:
            bank_trap = True
        
        if asset.provision_coverage is not None and asset.provision_coverage < 1.3:
            bank_trap = True
            
        return base_trap or bank_trap

    return base_trap

def calculate_payout_score(asset: AssetFundamentals) -> int:
    """
    模块三 part 2: 价值兑现评分 (Payout Score)
    Range: -2 to +2
    """
    # 1. 股息分 (Dividend Score)
    div_score = 0
    y = asset.dividend_yield
    if y >= 0.04:
        div_score = 1
    elif y >= 0.02:
        div_score = 0
    else:
        div_score = -1
        
    # 2. 回购分 (Buyback Score)
    buyback_score = 0
    r = asset.buyback_ratio
    if r >= 0.03:
        buyback_score = 1
    elif r >= 0.01:
        buyback_score = 0
    else:
        buyback_score = -1
        
    # 3. 负面修正 (Negative Correction)
    # 若 valuation_status == "Overvalued" 且有回购 (ratio >= 1%)，回购分强制 -1
    # 逻辑：高位回购毁灭价值
    if asset.valuation_status == "Overvalued" and r >= 0.01:
        buyback_score = -1
        
    # 4. 总分
    return div_score + buyback_score
