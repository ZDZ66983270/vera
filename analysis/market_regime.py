import pandas as pd
from data.price_cache import load_price_series
from metrics.risk_engine import RiskEngine
from config import DEFAULT_MARKET_INDEX, SECONDARY_GROWTH_INDEX, SECONDARY_VALUE_INDEX
# NEW: Import position/amplification calculators
from analysis.position_rs import calculate_position_pct, calculate_market_amplification
from db.market_sector_snapshot import save_market_risk_metrics

RS_LOOKBACK_DAYS = 63  # ~3m
MARKET_LOOKBACK_DAYS = 3650 # ~10y, 确保覆盖大行情高点

def _to_close_series(df: pd.DataFrame) -> pd.Series:
    df = df.copy()
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    df = df.sort_values("trade_date")
    df = df.set_index("trade_date")
    return df["close"].astype(float)

def _relative_strength(a: pd.Series, b: pd.Series, lookback_days: int) -> float | None:
    x = pd.concat([a, b], axis=1).dropna()
    if len(x) < lookback_days + 5:
        return None
    ratio = x.iloc[:, 0] / x.iloc[:, 1]
    return float(ratio.iloc[-1] / ratio.iloc[-lookback_days] - 1.0)

def build_market_regime(
    as_of_date: str, 
    asset_id: str = "^GSPC", 
    growth_proxy: str = SECONDARY_GROWTH_INDEX,
    value_proxy: str = SECONDARY_VALUE_INDEX,
    snapshot_id: str = None
) -> dict:
    """
    Build market regime overlay with NEW Position and Amplification metrics
    
    Args:
        as_of_date: Date string (YYYY-MM-DD)
        asset_id: Market index ID
        snapshot_id: UUID of parent snapshot (for persistence)
    
    Returns:
        Dict with market metrics including new position_pct and amplification
    """
    end = pd.to_datetime(as_of_date)
    start = (end - pd.Timedelta(days=MARKET_LOOKBACK_DAYS)).strftime("%Y-%m-%d")
    
    # 1. Load Market Index Data
    market_df = load_price_series(asset_id, start, as_of_date)
    spx_df = market_df # Alias for logic below

    ndx_df = load_price_series(growth_proxy, start, as_of_date) if growth_proxy else None
    dji_df = load_price_series(value_proxy, start, as_of_date) if value_proxy else None
    
    if market_df is None or market_df.empty:
        return {
            "market_index_id": asset_id,
            "market_dd_state": "D0 (Data Missing)",
            "market_regime_label": "Unknown"
        }

    spx = _to_close_series(spx_df)
    spx_risk = RiskEngine.calculate_risk_metrics(spx)
    
    rs_g = None
    rs_v = None
    
    if ndx_df is not None and not ndx_df.empty:
        rs_g = _relative_strength(_to_close_series(ndx_df), spx, RS_LOOKBACK_DAYS)
        
    if dji_df is not None and not dji_df.empty:
        rs_v = _relative_strength(_to_close_series(dji_df), spx, RS_LOOKBACK_DAYS)
    
    # NEW: Calculate Market Position (10Y percentile)
    market_position_pct = calculate_position_pct(asset_id, as_of_date)
    
    # Check if RiskEngine returned valid state
    mkt_dd = (spx_risk.get("risk_state") or {}).get("state")
    mkt_path = spx_risk.get("path_risk_level")
    volatility = spx_risk.get("annual_volatility", 0.0)
    
    # NEW: Calculate Market Amplification (MVP version)
    amplification_level, amplification_score = calculate_market_amplification(
        market_dd_state=mkt_dd or "D0",
        volatility=volatility or 0.0,
        market_position_pct=market_position_pct
    )
    
    # Regime label (existing logic)
    label = "Healthy Differentiation"
    
    if mkt_dd in ("D4", "D5") or mkt_path == "HIGH":
        label = "Systemic Stress"
    elif rs_g is not None and rs_v is not None and rs_g < -0.05 and rs_v < -0.05:
        label = "Systemic Compression"
    
    # NEW: Persist to market_risk_snapshot table
    if snapshot_id:
        try:
            save_market_risk_metrics(
                snapshot_id=snapshot_id,
                index_asset_id=asset_id,
                as_of_date=as_of_date,
                index_risk_state=mkt_dd or "D0",
                drawdown=spx_risk.get("current_drawdown", 0.0),
                volatility=volatility,
                market_position_pct=market_position_pct,
                market_amplification_level=amplification_level,
                market_amplification_score=amplification_score
            )
        except Exception as e:
            print(f"Warning: Failed to save market risk metrics: {e}")
    
    return {
        "market_index_id": asset_id,
        "market_dd_state": mkt_dd,
        "market_recent_cycle": (spx_risk.get("risk_state") or {}).get("recent_cycle"),
        "market_path_risk": mkt_path,
        "market_position_pct": market_position_pct,  # NEW
        "market_amplification_level": amplification_level,  # NEW
        "market_amplification_score": amplification_score,  # NEW
        "growth_vs_market_rs_3m": rs_g,
        "value_vs_market_rs_3m": rs_v,
        "market_regime_label": label,
        "market_volatility_1y": spx_risk.get("volatility_1y"),
        "market_drawdown": (spx_risk.get("risk_state") or {}).get("drawdown"),
    }
