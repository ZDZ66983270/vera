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
                ind_dd_state, ind_path_risk, ind_vol_regime, ind_position_pct, ind_drawdown,
                sector_etf_id, sector_dd_state, sector_path_risk, stock_vs_sector_rs_3m, sector_alignment, sector_drawdown,
                market_index_id, market_dd_state, market_path_risk, growth_vs_market_rs_3m, value_vs_market_rs_3m, market_regime_label, market_drawdown,
                overlay_summary, overlay_flags, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            snapshot_id, 
            asset_id, 
            as_of_date,
            ind.get("state"), 
            ind.get("path_risk"), 
            ind.get("vol_regime"), 
            ind.get("position_pct"),
            json.dumps(ind.get("drawdown") or {}),
            
            sec.get("id"), 
            sec.get("state"), 
            sec.get("path_risk"), 
            sec.get("stock_vs_sector_rs_3m"), 
            sec.get("sector_alignment"),
            json.dumps(sec.get("drawdown") or {}),
            
            mkt.get("id"), 
            mkt.get("state"), 
            mkt.get("path_risk"), 
            mkt.get("growth_vs_market_rs_3m"), 
            mkt.get("value_vs_market_rs_3m"), 
            mkt.get("market_regime_label"),
            json.dumps(mkt.get("drawdown") or {}),
            
            summary, 
            flags_json, 
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
        conn.commit()
    finally:
        conn.close()
