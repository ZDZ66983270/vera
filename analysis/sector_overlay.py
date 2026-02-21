import pandas as pd
from db.connection import get_connection
from data.price_cache import load_price_series
from metrics.risk_engine import RiskEngine
# NEW: Import position/RS calculators
from analysis.position_rs import calculate_position_pct, calculate_sector_rs_3m
from db.market_sector_snapshot import save_sector_risk_snapshot

RS_LOOKBACK_DAYS = 63
SECTOR_LOOKBACK_DAYS = 3650 # ~10Y

def _to_close_series(df: pd.DataFrame) -> pd.Series:
    df = df.copy()
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    df = df.sort_values("trade_date").set_index("trade_date")
    return df["close"].astype(float)

def _relative_strength(a: pd.Series, b: pd.Series, lookback_days: int) -> float | None:
    x = pd.concat([a, b], axis=1).dropna()
    if len(x) < lookback_days + 5:
        return None
    ratio = x.iloc[:, 0] / x.iloc[:, 1]
    return float(ratio.iloc[-1] / ratio.iloc[-lookback_days] - 1.0)


def build_sector_overlay(
    asset_id: str, 
    as_of_date: str, 
    proxy_etf_id: str = None, 
    sector_name: str = None,
    market_index_id: str = "^GSPC",
    snapshot_id: str = None
) -> dict:
    """
    Build sector overlay with NEW Position and RS metrics
    
    Args:
        asset_id: Individual stock asset ID
        as_of_date: Date string (YYYY-MM-DD)
        proxy_etf_id: Sector ETF ID
        sector_name: Sector name string
        market_index_id: Market index ID for RS calculation
        snapshot_id: UUID of parent snapshot (for persistence)
    
    Returns:
        Dict with sector metrics including new position_pct and sector_rs_3m
    """
    # 1. If no proxy provided, try to return empty or fallback (legacy support removed for clarity)
    if not proxy_etf_id:
        return {"sector_etf_id": None, "reason": "No proxy_etf_id provided"}
    
    sector_etf_id = proxy_etf_id

    end = pd.to_datetime(as_of_date)
    start = (end - pd.Timedelta(days=SECTOR_LOOKBACK_DAYS)).strftime("%Y-%m-%d")

    stock_df = load_price_series(asset_id, start, as_of_date)
    sector_df = load_price_series(sector_etf_id, start, as_of_date)

    if stock_df is None or stock_df.empty:
        return {"sector_etf_id": sector_etf_id, "sector_name": sector_name, "reason": "stock price missing"}
        
    if sector_df is None or sector_df.empty:
        return {"sector_etf_id": sector_etf_id, "sector_name": sector_name, "reason": "sector price missing"}

    stock = _to_close_series(stock_df)
    sector = _to_close_series(sector_df)

    sec_risk = RiskEngine.calculate_risk_metrics(sector)
    
    # Existing: Stock vs Sector RS
    stock_vs_sector_rs_3m = _relative_strength(stock, sector, RS_LOOKBACK_DAYS)
    
    # NEW: Sector Position (10Y percentile)
    sector_position_pct = calculate_position_pct(sector_etf_id, as_of_date)
    
    # NEW: Sector RS vs Market
    sector_vs_market_rs_3m = calculate_sector_rs_3m(sector_etf_id, market_index_id, as_of_date)
    
    sector_dd = (sec_risk.get("risk_state") or {}).get("state")
    sector_path = sec_risk.get("path_risk_level")
    
    # alignment 简化：跑输板块且个股更差 => negative_divergence
    alignment = "aligned"
    if stock_vs_sector_rs_3m is not None:
        if stock_vs_sector_rs_3m < -0.05:
            alignment = "negative_divergence"
        elif stock_vs_sector_rs_3m > 0.05:
            alignment = "positive_divergence"
    
    # NEW: Persist to sector_risk_snapshot table
    if snapshot_id:
        try:
            save_sector_risk_snapshot(
                snapshot_id=snapshot_id,
                sector_etf_id=sector_etf_id,
                as_of_date=as_of_date,
                sector_dd_state=sector_dd,
                sector_position_pct=sector_position_pct,
                sector_rs_3m=sector_vs_market_rs_3m
            )
        except Exception as e:
            print(f"Warning: Failed to save sector risk snapshot: {e}")

    return {
        "sector_etf_id": sector_etf_id,
        "sector_name": sector_name,
        "sector_dd_state": sector_dd,
        "sector_recent_cycle": (sec_risk.get("risk_state") or {}).get("recent_cycle"),
        "sector_path_risk": sector_path,
        "sector_position_pct": sector_position_pct,  # NEW
        "sector_vs_market_rs_3m": sector_vs_market_rs_3m,  # NEW (Sector RS)
        "stock_vs_sector_rs_3m": stock_vs_sector_rs_3m,  # Existing (Stock vs Sector)
        "sector_alignment": alignment,
        "sector_volatility_1y": sec_risk.get("volatility_1y"),
        "sector_drawdown": (sec_risk.get("risk_state") or {}).get("drawdown"),
    }
