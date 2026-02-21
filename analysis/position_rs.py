"""
Market and Sector Position/RS calculation utilities
Following frozen specifications from implementation plan
"""
import pandas as pd
from scipy.stats import percentileofscore
from data.price_cache import load_price_series
from config import DEFAULT_LOOKBACK_YEARS

MIN_TRADING_DAYS = 126  # Relaxed to 6 months for MVP (was 3 years)
RS_3M_DAYS = 63  # 3 months = 63 trading days


def calculate_position_pct(asset_id: str, as_of_date: str, lookback_years: int = None) -> float | None:
    """
    Calculate position percentile for market index or sector ETF
    
    Args:
        asset_id: Asset ID (market index or sector ETF)
        as_of_date: Date to calculate position for (YYYY-MM-DD)
        lookback_years: Years of history to use (default: DEFAULT_LOOKBACK_YEARS)
    
    Returns:
        Float in [0.0, 1.0] representing percentile, or None if insufficient data
    
    Spec:
        - Lookback: DEFAULT_LOOKBACK_YEARS (10Y)
        - Minimum data: 252*3 days (3 years)
        - Definition: Percentile rank of current price vs historical close distribution
        - Missing data: Return None (NOT 0.0)
    """
    if lookback_years is None:
        lookback_years = DEFAULT_LOOKBACK_YEARS
    
    # Calculate start date
    end = pd.to_datetime(as_of_date)
    start = (end - pd.Timedelta(days=lookback_years * 365)).strftime("%Y-%m-%d")
    
    # Load price series
    df = load_price_series(asset_id, start, as_of_date)
    
    if df is None or df.empty or len(df) < MIN_TRADING_DAYS:
        return None
    
    # Extract close prices
    prices = df['close'].astype(float)
    current_price = prices.iloc[-1]
    
    # Calculate percentile using scipy
    percentile = percentileofscore(prices, current_price, kind='rank') / 100.0
    
    return float(percentile)


def calculate_sector_rs_3m(sector_etf_id: str, market_index_id: str, as_of_date: str) -> float | None:
    """
    Calculate Sector RS (Relative Strength) vs Market for 3 months
    
    Args:
        sector_etf_id: Sector ETF asset ID
        market_index_id: Market index asset ID
        as_of_date: Date to calculate RS for (YYYY-MM-DD)
    
    Returns:
        Float representing RS (can be negative), or None if insufficient data
    
    Spec:
        - Period: RS_3M = 63 trading days (NOT natural months)
        - Return Type: Simple return (NOT log return)
        - Price Source: Close price (unadjusted)
        - Formula: RS_3M = (sector_t / sector_{t-63} - 1) - (market_t / market_{t-63} - 1)
    """
    # Load price series for both assets
    end = pd.to_datetime(as_of_date)
    # Need extra buffer for lookback
    start = (end - pd.Timedelta(days=RS_3M_DAYS * 2)).strftime("%Y-%m-%d")
    
    sector_df = load_price_series(sector_etf_id, start, as_of_date)
    market_df = load_price_series(market_index_id, start, as_of_date)
    
    if sector_df is None or sector_df.empty or len(sector_df) < RS_3M_DAYS + 5:
        return None
    if market_df is None or market_df.empty or len(market_df) < RS_3M_DAYS + 5:
        return None
    
    # Extract close prices
    sector_close = sector_df['close'].astype(float)
    market_close = market_df['close'].astype(float)
    
    # Calculate simple returns over 63 trading days
    sector_return = (sector_close.iloc[-1] / sector_close.iloc[-RS_3M_DAYS] - 1)
    market_return = (market_close.iloc[-1] / market_close.iloc[-RS_3M_DAYS] - 1)
    
    # Relative strength = sector return - market return
    rs_3m = sector_return - market_return
    
    return float(rs_3m)


def calculate_market_amplification(
    market_dd_state: str,
    volatility: float,
    market_position_pct: float = None
) -> tuple[str, float]:
    """
    Calculate Market Amplification Level (MVP version)
    
    Args:
        market_dd_state: Drawdown state (D0-D5)
        volatility: Annualized volatility (0.0-1.0 scale)
        market_position_pct: Market position percentile (optional, for score)
    
    Returns:
        Tuple of (level: str, score: float)
        - level: 'LOW', 'MID', or 'HIGH'
        - score: 0-100
    
    Spec (MVP - No Dispersion dependency):
        - HIGH: dd_state in ('D3','D4','D5','D6') OR volatility > 0.35
        - MID:  dd_state == 'D2' OR 0.25 <= volatility <= 0.35
        - LOW:  dd_state in ('D0','D1') AND volatility < 0.25
    
    Score (0-100):
        score = 0.4*dd_severity + 0.4*vol_bucket + 0.2*pos_bucket
    """
    # Determine level
    if market_dd_state in ('D3', 'D4', 'D5', 'D6') or volatility > 0.35:
        level = 'HIGH'
    elif market_dd_state == 'D2' or (0.25 <= volatility <= 0.35):
        level = 'MID'
    else:  # D0, D1 and vol < 0.25
        level = 'LOW'
    
    # Calculate score components
    dd_severity_map = {'D0': 0, 'D1': 20, 'D2': 40, 'D3': 60, 'D4': 80, 'D5': 100, 'D6': 120}
    dd_severity = dd_severity_map.get(market_dd_state, 50)
    
    vol_bucket = min(100, volatility * 200)  # 0.5 vol = 100
    
    pos_bucket = 0
    if market_position_pct is not None:
        pos_bucket = market_position_pct * 100
    
    # Weighted score
    score = 0.4 * dd_severity + 0.4 * vol_bucket + 0.2 * pos_bucket
    
    return level, float(score)
