from dataclasses import dataclass
from typing import Optional
import pandas as pd

"""
=== Currency Conversion & Data Consistency (ADR/HK Dual Currency) ===

1. Data Source Discrepancy:
   - Financial Reports (Revenue, Net Income, Cash Flow) are stored in 'Reporting Currency' (e.g., CNY for BABA/TSM/00700).
   - Stock Prices (Close, Market Cap) are in 'Trading Currency' (e.g., USD for ADRs, HKD for HK Stocks).

2. Valuation Ratios (PE, PB, PS):
   - We prioritize ratios sourced directly from Market Data Providers (e.g., Yahoo Finance, AkShare).
   - These providers handle the currency matching internally (e.g., Price_USD / EPS_USD).
   - Therefore, 'pe_ttm', 'pb_ratio' in `AssetFundamentals` are currency-consistent.

3. Cross-Calculation Rule:
    - IF calculating ratios manually (e.g., Price / EPS_from_DB), YOU MUST APPLY FX RATE.
      Formula: Ratio = Price_Trading / (EPS_Reporting * FX_Rate_Reporting_to_Trading)
    - To avoid FX errors, this module prefers deriving 'Trading EPS' via `Price / PE` (Market Source),
      rather than `NetIncome / Shares`.

4. Specific Cases:
   - ADRs (US): Price=USD, Financials=Local (CNY/TWD). Conversion required for aggregations.
   - HK Stocks (Mainland): Price=HKD, Financials=CNY. Conversion `CNY -> HKD` required.
"""

@dataclass
class AssetFundamentals:
    """
    资产基本面数据结构，用于承载分析所需字段
    """
    symbol: str
    industry: str
    
    # TTM Data
    net_profit_ttm: float
    revenue_ttm: float
    
    # Growth Data (3 Year CAGR)
    # 如果没有数据，可以是 None
    revenue_growth_3y: Optional[float] = None
    profit_growth_3y: Optional[float] = None
    
    # Valuation & Yield
    pe_ttm: Optional[float] = None
    pe_static: Optional[float] = None  # NEW: Static PE (Anchor)
    pb_ratio: Optional[float] = None
    dividend_yield: float = 0.0  # e.g. 0.05 for 5%
    buyback_ratio: float = 0.0   # e.g. 0.03 for 3%
    # Valuation Status (calculated externally or passed in)
    # "Undervalued", "Fair", "Overvalued"
    valuation_status: str = "Fair"
    
    bps: Optional[float] = None # Book value per share
    eps_ttm: Optional[float] = None # Earnings per share (TTM)
    
    # Multi-year historical data for quality assessment
    revenue_history: Optional[list] = None  # List of annual revenues (oldest to newest)
    roe: Optional[float] = None  # Return on Equity
    net_margin: Optional[float] = None  # Net Profit Margin
    
    # Payout Policy Context (for Quality Assessment)
    no_dividend_history: bool = False  # True if company has trading history but never paid dividends
    listing_years: Optional[float] = None  # Approximate years since listing
    
    npl_deviation: Optional[float] = None      # 不良偏离度 (Overdue90 / NPL)
    provision_coverage: Optional[float] = None # 拨备覆盖率 (e.g. 2.50)
    
    # New VERA 2.5 Bank metrics
    net_interest_income: Optional[float] = None
    net_fee_income: Optional[float] = None
    provision_expense: Optional[float] = None
    total_loans: Optional[float] = None
    core_tier1_capital_ratio: Optional[float] = None

def choose_valuation_anchor(asset: AssetFundamentals) -> str:
    """
    模块二：估值锚自动选择引擎
    Logic:
      1. 盈利性检查 (亏损看 PS)
      2. 资产属性检查 (金融/地产/公用事业看 PB)
      3. 默认 (PE)
    """
    # 1. 盈利性检查
    if asset.net_profit_ttm <= 0:
        return "PS"
        
    # 2. 资产属性检查
    # 注意：这里需要确保行业名称归一化，或者使用模糊匹配
    special_industries = ["Bank", "Insurance", "RealEstate", "Utility"]
    if asset.industry in special_industries:
        return "PB"
        
    # 3. 默认情况

def get_valuation_status(percentile: float) -> str:
    """
    根据 10 年 PE 分位定义估值状态
    Low: 0-20%
    Fair: 20-80%
    Overvalued: 80-95%
    Extreme: >95%
    """
    if percentile is None: return "Unknown"
    if percentile <= 20: return "Undervalued"
    if percentile >= 95: return "Extreme"
    if percentile >= 80: return "Overvalued"
    return "Fair"

def analyze_valuation_path(
    pe_series: list[float], 
    price_series: list[float], 
    dates: list[str]
) -> dict:
    """
    估值路径分析 (10Y Lookback)
    判定当前下跌是 'Valuation Kill' (杀估值) 还是 'Earnings Kill' (杀业绩)
    
    Logic:
      1. Find Price Peak in last 10 years (or available history).
      2. If current price is not significantly down from peak (<20%), return Normal.
      3. Compare PE drop ratio vs Price drop ratio.
    
    Returns:
        {
            "path_type": "Normal" | "Valuation Kill" | "Earnings Kill" | "Mixed",
            "peak_date": str,
            "peak_price": float,
            "peak_pe": float,
            "drawdown_pct": float,
            "pe_drop_contribution": float  # 估值收缩贡献度
        }
    """
    if not pe_series or not price_series or len(pe_series) != len(price_series):
        return {"path_type": "Normal"}
    
    # Ensure working with recent 10 years (assuming data passed is already within reasonable range, 
    # but strictly speaking we should filter if full history is passed. 
    # For now, we assume caller passes the relevant 10Y window or we check length).
    # Simple list operations for portability.
    
    # 1. Find Peak Price
    # We iterate to find max price and its index
    max_p = -1.0
    max_idx = -1
    for i, p in enumerate(price_series):
        if p is not None and p > max_p:
            max_p = p
            max_idx = i
            
    if max_idx == -1:
        return {"path_type": "Normal"}
        
    peak_price = max_p
    peak_date = dates[max_idx] if max_idx < len(dates) else "Unknown"
    peak_pe = pe_series[max_idx]
    
    curr_price = price_series[-1]
    curr_pe = pe_series[-1]
    
    # Avoid zero division
    if not peak_price or peak_price == 0:
        return {"path_type": "Normal"}
        
    # 2. Calculate Drawdown
    dd_pct = (peak_price - curr_price) / peak_price
    
    if dd_pct < 0.20: # Drawdown less than 20% is not considered a "Kill" context
        return {"path_type": "Normal"}
        
    # 3. Analyze Drivers
    # Price = PE * EPS  =>  log(P) = log(PE) + log(EPS)
    # Roughly: %d P ~= %d PE + %d EPS
    
    # Calculate drops
    price_drop = dd_pct # Positive value for drop
    
    # PE Drop
    if peak_pe and peak_pe > 0:
        pe_change = (peak_pe - curr_pe) / peak_pe
    else:
        pe_change = 0
        
    # EPS Drop (implied)
    # If Price dropped 50% and PE dropped 50%, then EPS is stable (0% drop).
    # If Price dropped 50% and PE is same, EPS dropped 50%.
    
    # We define Contribution:
    # Valuation Kill Ratio = PE_change / Price_drop
    # If PE dropped 40% while Price dropped 50% -> 0.8 -> Mainly Valuation
    
    val_kill_ratio = 0.0
    if price_drop > 0:
        val_kill_ratio = pe_change / price_drop
        
    # Determination
    path_type = "Mixed"
    if val_kill_ratio > 0.7:
        path_type = "Valuation Kill" # 杀估值
    elif val_kill_ratio < 0.3:
        path_type = "Earnings Kill"  # 杀业绩 (PE drop is small part of Price drop)
        
    return {
        "path_type": path_type,
        "peak_date": peak_date,
        "peak_price": peak_price,
        "peak_pe": peak_pe,
        "drawdown_pct": dd_pct,
        "pe_drop_contribution": val_kill_ratio
    }

def get_valuation_history(asset_id: str, years: int = 5, start_date=None, end_date=None) -> pd.DataFrame:
    """
    获取资产的估值历史数据 (Price & PE)
    直接从 vera_price_cache 读取，不做 EPS 推导
    """
    from db.connection import get_connection
    from datetime import datetime, timedelta, date
    
    conn = get_connection()
    try:
        # Determine Query Parameters
        params = [asset_id]
        
        # 1. Start Date Logic
        # If explicit start_date provided, use it. Otherwise loopback 'years'.
        if start_date:
            # Handle date obj vs string
            s_date_str = start_date.strftime("%Y-%m-%d") if isinstance(start_date, (datetime, date)) else str(start_date)
        else:
            s_date_str = (datetime.now() - timedelta(days=years*365)).strftime("%Y-%m-%d")
        
        params.append(s_date_str)
        
        # 2. End Date Logic (Optional)
        date_filter_sql = "AND trade_date >= ?"
        if end_date:
            e_date_str = end_date.strftime("%Y-%m-%d") if isinstance(end_date, (datetime, date)) else str(end_date)
            date_filter_sql += " AND trade_date <= ?"
            params.append(e_date_str)
        
        # Query Price Cache
        # Prefer pe_ttm, fallback to pe
        query = f"""
        SELECT 
            trade_date, 
            close as price, 
            COALESCE(pe_ttm, pe) as pe
        FROM vera_price_cache 
        WHERE symbol = ? 
          {date_filter_sql}
        ORDER BY trade_date ASC
        """
        
        df = pd.read_sql_query(query, conn, params=params)
        
        if df.empty:
            return pd.DataFrame()
            
        # Data Cleaning
        df['trade_date'] = pd.to_datetime(df['trade_date'])
        
        # Forward fill PE to handle gaps (common in daily data if PE is updated less frequently)
        df['pe'] = df['pe'].ffill()
        
        # --- Derive EPS & Calculate Momentum for Driver Analysis ---
        # 1. Calculate EPS
        df['eps'] = df['price'] / df['pe']
        
        # 2. Rolling Momentum (60 days ~ 3 months)
        # Using shift(60) for daily data
        df['price_mom'] = df['price'].pct_change(60)
        df['pe_mom'] = df['pe'].pct_change(60)
        df['eps_mom'] = df['eps'].pct_change(60)
        
        # 3. Determine Driver Phase
        # Logic:
        # - Overheated (Red): Price Up (>5%) AND PE Expansion > EPS Growth
        # - Healthy (Green): Price Up (>5%) AND EPS Growth >= PE Expansion
        # - Neutral (Grey): Price Flat/Down or Data insufficient
        
        def classify_phase(row):
            if pd.isna(row['price_mom']) or row['price_mom'] <= 0.05:
                return "Neutral"
            
            # Uptrend Scenario
            # Fix: If PE or EPS data is missing, cannot determine driver -> Neutral
            if pd.isna(row['pe_mom']) or pd.isna(row['eps_mom']):
                return "Neutral"

            # Compare contributions. 
            # Note: (1+r_P) ~= (1+r_PE) * (1+r_EPS)
            # Roughly comparing magnitude of % change works.
            
            if row['pe_mom'] > row['eps_mom']:
                return "Overheated" # 拔估值
            else:
                return "Healthy" # 业绩兑现
                
        df['driver_phase'] = df.apply(classify_phase, axis=1)
        
        return df
        
    except Exception as e:
        print(f"Error fetching valuation history for {asset_id}: {e}")
        return pd.DataFrame()
    finally:
        conn.close()
