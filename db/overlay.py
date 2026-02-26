from datetime import datetime
from db.connection import get_connection

def save_risk_overlay_snapshot(
    snapshot_id: str, 
    asset_id: str, 
    as_of_date: str,
    ind: dict, 
    sec: dict, 
    mkt: dict, 
    summary: str, 
    flags_json: str
):
    import json
    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO risk_overlay_snapshot (
                snapshot_id, asset_id, as_of_date,
                ind_dd_state, ind_label_zh, ind_path_risk, ind_vol_regime, ind_position_pct, ind_volatility_1y, ind_drawdown, ind_recent_cycle,
                sector_etf_id, sector_dd_state, sector_label_zh, sector_path_risk, stock_vs_sector_rs_3m, sector_alignment, sector_volatility_1y, sector_drawdown, sector_recent_cycle,
                market_index_id, market_dd_state, market_label_zh, market_path_risk, growth_vs_market_rs_3m, value_vs_market_rs_3m, market_regime_label, market_volatility_1y, market_drawdown, market_recent_cycle,
                overlay_summary, overlay_flags, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            snapshot_id, 
            asset_id, 
            as_of_date,
            ind.get("state"), 
            ind.get("label_zh"),
            ind.get("path_risk"), 
            ind.get("vol_regime"), 
            ind.get("position_pct"),
            ind.get("volatility_1y"),
            json.dumps(ind.get("drawdown") or {}),
            json.dumps(ind.get("recent_cycle") or {}),
            
            sec.get("id"), 
            sec.get("state"), 
            sec.get("label_zh"),
            sec.get("path_risk"), 
            sec.get("stock_vs_sector_rs_3m"), 
            sec.get("sector_alignment"),
            sec.get("volatility_1y"),
            json.dumps(sec.get("drawdown") or {}),
            json.dumps(sec.get("recent_cycle") or {}),
            
            mkt.get("id"), 
            mkt.get("state"), 
            mkt.get("label_zh"),
            mkt.get("path_risk"), 
            mkt.get("growth_vs_market_rs_3m"), 
            mkt.get("value_vs_market_rs_3m"), 
            mkt.get("market_regime_label"),
            mkt.get("volatility_1y"),
            json.dumps(mkt.get("drawdown") or {}),
            json.dumps(mkt.get("recent_cycle") or {}),
            
            summary, 
            flags_json, 
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
        conn.commit()
    finally:
        conn.close()
