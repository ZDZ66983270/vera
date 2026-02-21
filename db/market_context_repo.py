
# db/market_context_repo.py
import json
from db.connection import get_connection

def save_market_context(snapshot_id: str, symbol: str, market_index_symbol: str, amplifier: dict, alpha: dict, regime_label: str):
    """
    Persist to risk_card_snapshot additional columns if present.
    """
    notes = {
        "market_amplifier": amplifier,
        "alpha_headroom": alpha,
    }
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE risk_card_snapshot
            SET market_index_asset_id = ?,
                market_amplification_level = ?,
                alpha_headroom = ?,
                market_regime_label = ?,
                market_regime_notes = ?
            WHERE snapshot_id = ?
            """,
            (
                market_index_symbol,
                amplifier.get("amplification_level"),
                alpha.get("alpha_headroom"),
                regime_label,
                json.dumps(notes, ensure_ascii=False),
                snapshot_id
            )
        )
        conn.commit()
        conn.close()
    except Exception:
        # don't block snapshot
        pass
