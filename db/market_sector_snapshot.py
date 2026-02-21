"""
Database persistence for market and sector risk snapshots
"""
from datetime import datetime
from db.connection import get_connection


def save_market_risk_metrics(
    snapshot_id: str,
    index_asset_id: str,
    as_of_date: str,
    index_risk_state: str,
    drawdown: float,
    volatility: float,
    market_position_pct: float = None,
    market_amplification_level: str = None,
    market_amplification_score: float = None
):
    """
    Save market risk metrics to market_risk_snapshot table
    
    Note: This function UPDATES or INSERTS the extended metrics
    into the existing market_risk_snapshot row.
    """
    conn = get_connection()
    try:
        # Check if record exists
        existing = conn.execute("""
            SELECT id FROM market_risk_snapshot
            WHERE index_asset_id = ? AND as_of_date = ?
        """, (index_asset_id, as_of_date)).fetchone()
        
        if existing:
            # UPDATE existing record with new metrics
            conn.execute("""
                UPDATE market_risk_snapshot
                SET market_position_pct = ?,
                    market_amplification_level = ?,
                    market_amplification_score = ?
                WHERE index_asset_id = ? AND as_of_date = ?
            """, (
                market_position_pct,
                market_amplification_level,
                market_amplification_score,
                index_asset_id,
                as_of_date
            ))
        else:
            # INSERT new record
            conn.execute("""
                INSERT INTO market_risk_snapshot (
                    index_asset_id, as_of_date, index_risk_state, drawdown, volatility,
                    market_position_pct, market_amplification_level, market_amplification_score,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                index_asset_id, as_of_date, index_risk_state, drawdown, volatility,
                market_position_pct, market_amplification_level, market_amplification_score,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ))
        
        conn.commit()
    finally:
        conn.close()


def save_sector_risk_snapshot(
    snapshot_id: str,
    sector_etf_id: str,
    as_of_date: str,
    sector_dd_state: str = None,
    sector_position_pct: float = None,
    sector_rs_3m: float = None
):
    """
    Save sector risk metrics to sector_risk_snapshot table
    
    Args:
        snapshot_id: UUID of the parent asset snapshot
        sector_etf_id: Sector ETF asset ID
        as_of_date: Date (YYYY-MM-DD)
        sector_dd_state: Drawdown state of sector ETF
        sector_position_pct: Position percentile [0.0-1.0]
        sector_rs_3m: Relative strength vs market for 3M
    """
    conn = get_connection()
    try:
        conn.execute("""
            INSERT OR REPLACE INTO sector_risk_snapshot (
                snapshot_id, sector_etf_id, as_of_date,
                sector_dd_state, sector_position_pct, sector_rs_3m,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            snapshot_id, sector_etf_id, as_of_date,
            sector_dd_state, sector_position_pct, sector_rs_3m,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
        conn.commit()
    finally:
        conn.close()
