
# market/index_risk.py
from datetime import datetime
from db.connection import get_connection
from metrics.risk_engine import RiskEngine

def _to_i_state(d_state: str) -> str:
    # D1-D5 -> I1-I5
    if isinstance(d_state, str) and d_state.startswith("D"):
        return "I" + d_state[1:]
    return d_state or "I3"

def get_or_compute_index_risk(index_symbol: str, as_of_date: datetime, price_loader, method_profile_id: str = "default"):
    """
    Uses market_risk_snapshot as cache.
    price_loader: function(symbol, start_date_str, end_date_str) -> DataFrame with trade_date, close, etc.
    """
    as_of_str = as_of_date.strftime("%Y-%m-%d")

    # 1) DB cache
    try:
        conn = get_connection()
        cur = conn.cursor()
        row = cur.execute(
            """
            SELECT index_risk_state, drawdown, volatility, volume_anomaly
            FROM market_risk_snapshot
            WHERE index_asset_id = ? AND as_of_date = ? AND method_profile_id = ?
            """,
            (index_symbol, as_of_str, method_profile_id)
        ).fetchone()
        conn.close()
        if row:
            return {
                "index_asset_id": index_symbol,
                "index_symbol": index_symbol,
                "as_of_date": as_of_str,
                "index_risk_state": row[0],
                "drawdown": row[1],
                "volatility": row[2],
                "volume_anomaly": row[3],
                "cached": True,
            }
    except Exception:
        # cache miss or table not present: proceed to compute
        pass

    # 2) compute from prices (10y window, consistent with your run_snapshot)
    start = (as_of_date.replace(hour=0, minute=0, second=0, microsecond=0) - __import__("datetime").timedelta(days=10*365)).strftime("%Y-%m-%d")
    end = as_of_str
    px = price_loader(index_symbol, start, end)
    if px is None or px.empty:
        return {
            "index_asset_id": index_symbol,
            "index_symbol": index_symbol,
            "as_of_date": as_of_str,
            "index_risk_state": "I3",
            "drawdown": None,
            "volatility": None,
            "volume_anomaly": None,
            "cached": False,
            "error": "no_price_data"
        }

    import pandas as pd
    px["trade_date"] = pd.to_datetime(px["trade_date"])
    px.set_index("trade_date", inplace=True)

    risk = RiskEngine.calculate_risk_metrics(px["close"])
    d_state = (risk.get("risk_state") or {}).get("state", "D3")
    i_state = _to_i_state(d_state)

    # drawdown/vol: reuse your computed fields if present
    dd = risk.get("current_drawdown") or risk.get("max_drawdown")
    vol = risk.get("annual_volatility")
    vol_anom = None  # optional later

    # 3) persist cache
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT OR REPLACE INTO market_risk_snapshot
            (index_asset_id, as_of_date, index_risk_state, drawdown, volatility, volume_anomaly, method_profile_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (index_symbol, as_of_str, i_state, dd, vol, vol_anom, method_profile_id)
        )
        conn.commit()
        conn.close()
    except Exception:
        pass

    return {
        "index_asset_id": index_symbol,
        "index_symbol": index_symbol,
        "as_of_date": as_of_str,
        "index_risk_state": i_state,
        "drawdown": dd,
        "volatility": vol,
        "volume_anomaly": vol_anom,
        "cached": False,
    }
