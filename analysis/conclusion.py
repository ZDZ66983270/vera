from dataclasses import dataclass
from typing import Optional

@dataclass
class ConclusionInput:
    """
    结论生成器的输入数据结构
    """
    # From Risk Engine
    max_drawdown: float
    annual_volatility: float
    
    # From Trap & Payout Engine
    is_value_trap: bool
    dividend_yield: float
    buyback_ratio: float
    
    # From Valuation Engine (or external calculation)
    valuation_status: str  # "Undervalued", "Fair", "Overvalued"
    
    # User Constraints
    user_max_drawdown_limit: float = 0.50  # 用户承受极限，默认 50%
    market_volatility_90_percentile: float = 0.60 # 市场波动率 90% 分位，默认 60%
    
    # Context
    industry: Optional[str] = None
    bank_quality_score: Optional[int] = None

def generate_conclusion(data: ConclusionInput) -> str:
    """
    模块 5: 统一结论生成器
    Logic:
      1. Hard Stop (Risk)
      2. Trap Check
      3. Synthesis (General vs Bank)
    """
    # 1. 一级否决 (Hard Stop)
    if data.max_drawdown < -abs(data.user_max_drawdown_limit):
        return "不适合 (历史回撤超出承受极限)"
        
    if data.annual_volatility > data.market_volatility_90_percentile:
        return "不适合 (波动率过高)"
        
    # 2. 陷阱检查
    if data.is_value_trap:
        if data.industry == "Bank":
            return "存在价值陷阱 (资产质量存疑)"
        return "存在价值陷阱 (高风险警示)"
        
    # 3. 综合判断
    v_status = data.valuation_status
    d_yield = data.dividend_yield
    
    # --- Bank Specific Logic ---
    if data.industry == "Bank" and data.bank_quality_score is not None:
        if data.bank_quality_score <= -1:
            # Note: is_value_trap handled above, but logic says "OR is_value_trap"
            # Here we are in the "not trap" branch (trap returned above), 
            # BUT the prompt logic implies we might want to catch score<=-1 here even if not trap?
            # Prompt: IF bank_quality_score <= -1 OR is_value_trap -> "存在陷阱"
            # Since we returned on trap above, we just handle score <= -1 here.
            return "存在陷阱 (不良认定宽松或拨备不足)"
            
        elif data.bank_quality_score >= 1 and v_status == "Undervalued":
            return "适合长期持有 (资产质量扎实，安全垫厚)"
            
        else:
            return "观察中"
    
    # --- General Logic ---
    if v_status == "Undervalued" and d_yield >= 0.04:
        return "适合长期持有 (利于分红 + 价格有安全垫)"
        
    if v_status == "Undervalued":
        return "适合分批买入 (估值优势)"
        
    if v_status == "Overvalued":
        return "暂不适合 (太贵)"
        
    # ELSE
    return "观察中"
