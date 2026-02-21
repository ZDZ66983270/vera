import warnings
import pandas as pd
from db.connection import get_connection
from utils.canonical_resolver import resolve_canonical_symbol


def save_daily_price(row: dict, *, auto_register_asset: bool = True):
    """
    写入 vera_price_cache 的唯一入口：
    - 先 resolve raw -> canonical
    - 再确保 canonical 存在于 assets（canonical 宇宙）
    - 最后写入 price_cache(symbol=canonical)
    
    ❗ RED LINE: DO NOT write raw symbols into vera_price_cache.symbol
    All symbols MUST be resolved to canonical_id via resolve_canonical_symbol()
    """
    conn = get_connection()
    cursor = conn.cursor()

    raw_symbol = (row.get("symbol") or "").strip().upper()
    if not raw_symbol:
        raise ValueError("row['symbol'] is required")

    # ❗ RED LINE: Resolve to canonical
    canonical_symbol = resolve_canonical_symbol(conn, raw_symbol)

    # ✅ Canonical whitelist: assets.asset_id
    exists = cursor.execute(
        "SELECT 1 FROM assets WHERE asset_id = ? LIMIT 1",
        (canonical_symbol,)
    ).fetchone()

    if not exists:
        if auto_register_asset:
            # Auto-register minimal asset record (補充 market/industry/roles later)
            cursor.execute(
                """
                INSERT OR IGNORE INTO assets (asset_id, symbol_name, market, industry, asset_type, index_role, asset_role, updated_at)
                VALUES (?, ?, 'Unknown', 'Unknown', 'Unknown', NULL, NULL, datetime('now'))
                """,
                (canonical_symbol, canonical_symbol)
            )
        else:
            raise ValueError(
                f"Canonical '{canonical_symbol}' not found in assets. "
                f"Please INSERT it into assets first."
            )

    # Source field: preserve raw audit trail
    source_name = row.get("source", "unknown")
    note = row.get("source_note")

    if raw_symbol != canonical_symbol:
        source = f"{source_name}|raw:{raw_symbol}"
        if note:
            source += f"|note:{note}"
    else:
        source = f"{source_name}|note:{note}" if note else source_name

    cursor.execute(
        """
        INSERT INTO vera_price_cache
        (symbol, trade_date, open, high, low, close, volume, source, pe, pe_ttm, pb, ps, eps)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol, trade_date) DO UPDATE SET
            open   = excluded.open,
            high   = excluded.high,
            low    = excluded.low,
            close  = excluded.close,
            volume = excluded.volume,
            source = excluded.source,
            pe     = excluded.pe,
            pe_ttm = excluded.pe_ttm,
            pb     = excluded.pb,
            ps     = excluded.ps,
            eps    = excluded.eps
        """,
        (
            canonical_symbol,
            row["trade_date"],
            row.get("open"),
            row.get("high"),
            row.get("low"),
            row["close"],
            int(row.get("volume") or 0),
            source,
            row.get("pe"),
            row.get("pe_ttm"),
            row.get("pb"),
            row.get("ps"),
            row.get("eps")
        )
    )

    conn.commit()
    conn.close()


def load_price_series(symbol: str, start_date: str, end_date: str):
    """
    唯一历史数据入口：
    - 输入 symbol 允许是 raw 或 canonical
    - 内部统一 resolve 成 canonical
    - 通过 asset_symbol_map 找到 price cache 中的实际 symbol
    - 从 vera_price_cache 读取
    """
    conn = get_connection()
    try:
        canonical = resolve_canonical_symbol(conn, (symbol or "").strip().upper())
        
        # In the normalized system, vera_price_cache.symbol ALWAYS uses the canonical_id
        price_symbol = canonical

        df = pd.read_sql_query(
            """
            SELECT trade_date, open, high, low, close, volume
            FROM vera_price_cache
            WHERE symbol = ? AND trade_date BETWEEN ? AND ?
            ORDER BY trade_date
            """,
            conn,
            params=(price_symbol, start_date, end_date)
        )
    finally:
        conn.close()

    if not df.empty:
        df = df.drop_duplicates(subset=["trade_date"], keep="last").sort_values("trade_date")

    return df
