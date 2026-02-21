import pandas as pd
import sqlite3
import argparse
import os
import glob

DB_PATH = "vera.db"

def get_connection():
    return sqlite3.connect(DB_PATH)

def _norm(s: str) -> str:
    return (s or "").strip().upper()

def _dedupe_df(df: pd.DataFrame, policy: str) -> pd.DataFrame:
    """
    DataFrame 内部去重：同一 (symbol, trade_date) 多行时如何处理
    """
    if df.empty:
        return df

    if policy == "keep_first":
        return df.drop_duplicates(subset=["symbol", "trade_date"], keep="first")
    # default keep_last
    return df.drop_duplicates(subset=["symbol", "trade_date"], keep="last")

def _precheck_ambiguity(conn, raw_symbols, asset_type_hint=None):
    """
    歧义预检查：在真正写库前先扫一遍 unique raw symbols。
    """
    from utils.canonical_resolver import resolve_canonical_symbol, AmbiguousSymbolError

    hint = _norm(asset_type_hint) if asset_type_hint else None
    ambiguous = []
    for rs in raw_symbols:
        try:
            resolve_canonical_symbol(
                conn, rs,
                asset_type_hint=hint,
                strict_ambiguous=True,
                strict_unknown=False,
                cn_namespace=True,
            )
        except AmbiguousSymbolError as e:
            ambiguous.append((rs, str(e)))

    if ambiguous:
        lines = ["[FATAL] Ambiguous symbols detected. Import aborted:"]
        for rs, err in ambiguous[:30]:
            lines.append(f"  - {rs}: {err}")
        lines.append("Fix options:")
        lines.append("  1) Provide --asset-type-hint INDEX|STOCK (for CN 6-digit codes)")
        lines.append("  2) Add unique mapping(s) in asset_symbol_map for the raw symbol(s)")
        raise SystemExit("\n".join(lines))

def _resolve_canonical_series(conn, raw_series: pd.Series, asset_type_hint=None) -> pd.Series:
    from utils.canonical_resolver import resolve_canonical_symbol
    hint = _norm(asset_type_hint) if asset_type_hint else None
    return raw_series.apply(lambda s: resolve_canonical_symbol(
        conn, s,
        asset_type_hint=hint,
        strict_ambiguous=True,
        strict_unknown=False,
        cn_namespace=True,
    ))

def _delete_existing_rows(conn, df: pd.DataFrame):
    """
    delete_then_insert：先删除即将写入的 (symbol, trade_date) 组合，再插入。
    """
    if df.empty:
        return
    cur = conn.cursor()

    # 批量删除：分批避免 SQLite 参数过多
    keys = list(df[["symbol", "trade_date"]].itertuples(index=False, name=None))
    chunk = 500
    for i in range(0, len(keys), chunk):
        sub = keys[i:i+chunk]
        # 构造 (symbol=? AND trade_date=?) OR (...) ...
        where = " OR ".join(["(symbol=? AND trade_date=?)"] * len(sub))
        params = []
        for sym, dt in sub:
            params.extend([sym, dt])
        cur.execute(f"DELETE FROM vera_price_cache WHERE {where}", params)

def _insert_rows(conn, df: pd.DataFrame, mode: str):
    cur = conn.cursor()

    if mode == "ignore":
        sql = """
            INSERT OR IGNORE INTO vera_price_cache
            (symbol, trade_date, open, high, low, close, volume, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
    elif mode == "fail":
        sql = """
            INSERT INTO vera_price_cache
            (symbol, trade_date, open, high, low, close, volume, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
    else:
        sql = """
            INSERT INTO vera_price_cache
            (symbol, trade_date, open, high, low, close, volume, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol, trade_date) DO UPDATE SET
                open   = excluded.open,
                high   = excluded.high,
                low    = excluded.low,
                close  = excluded.close,
                volume = excluded.volume,
                source = excluded.source
        """

    total = len(df)
    for i, r in enumerate(df.itertuples(index=False, name=None), start=1):
        # 0: symbol, 1: trade_date, 2: open, 3: high, 4: low, 5: close, 6: volume, 7: source
        cur.execute(sql, (
            r[0], r[1], r[2], r[3], r[4], r[5], int(r[6]), r[7]
        ))
        if i % 2000 == 0:
            print(f" ... processed {i}/{total}")

def parse_and_import(
    file_path: str,
    *,
    symbol_override: str | None = None,
    source_label: str = "manual_csv",
    mode: str = "upsert",
    dedupe: str = "keep_last",                 # keep_last | keep_first | delete_then_insert
    asset_type_hint: str | None = None,        # INDEX | STOCK
):
    print(f"[INFO] Processing {file_path} (mode={mode}, dedupe={dedupe})...")

    df = pd.read_csv(file_path)
    df.columns = [c.strip().lower() for c in df.columns]

    col_map = {
        'date':   ['date', 'time', 'timestamp', '日期', 'trade_date'],
        'close':  ['close', 'adj close', '收盘价', '成交价'],
        'open':   ['open', '开盘价'],
        'high':   ['high', '最高价'],
        'low':    ['low', '最低价'],
        'volume': ['volume', '成交量'],
        'symbol': ['symbol', 'ticker', 'code', '代码']
    }

    date_col  = next((c for c in df.columns if any(k in c for k in col_map['date'])), None)
    close_col = next((c for c in df.columns if any(k in c for k in col_map['close'])), None)
    if not date_col or not close_col:
        raise SystemExit(f"[ERROR] Missing required columns date/close. Found: {list(df.columns)}")

    clean = pd.DataFrame()
    clean["trade_date"] = pd.to_datetime(df[date_col]).dt.strftime("%Y-%m-%d")
    clean["close"] = pd.to_numeric(df[close_col], errors="coerce")

    for col in ["open", "high", "low"]:
        match = next((c for c in df.columns if any(k in c for k in col_map[col])), None)
        clean[col] = pd.to_numeric(df[match], errors="coerce") if match else clean["close"]

    vol_match = next((c for c in df.columns if any(k in c for k in col_map["volume"])), None)
    clean["volume"] = pd.to_numeric(df[vol_match], errors="coerce").fillna(0).astype(int) if vol_match else 0

    if symbol_override:
        clean["raw_symbol"] = _norm(symbol_override)
    else:
        sym_match = next((c for c in df.columns if any(k in c for k in col_map["symbol"])), None)
        if sym_match:
            clean["raw_symbol"] = df[sym_match].astype(str).map(_norm)
        else:
            guessed = os.path.splitext(os.path.basename(file_path))[0]
            clean["raw_symbol"] = _norm(guessed)
            print(f"[WARN] No symbol column. Using filename as raw_symbol: {clean['raw_symbol'].iloc[0]}")

    clean = clean.dropna(subset=["trade_date", "close", "raw_symbol"])
    if clean.empty:
        print("[WARN] No valid rows after cleaning.")
        return

    conn = get_connection()
    try:
        # 1) 歧义预检查（硬拦截）
        unique_raw = sorted(clean["raw_symbol"].unique().tolist())
        _precheck_ambiguity(conn, unique_raw, asset_type_hint=asset_type_hint)

        # 2) 映射到 canonical（写库只用 canonical）
        clean["symbol"] = _resolve_canonical_series(conn, clean["raw_symbol"], asset_type_hint=asset_type_hint)

        # 3) source 字段保留 raw 审计信息
        clean["source"] = clean["raw_symbol"].apply(lambda rs: f"{source_label}|raw:{rs}")

        # 4) DF 内部去重（避免同一文件内部重复行）
        clean = _dedupe_df(clean, policy=("keep_last" if dedupe == "delete_then_insert" else dedupe))

        # 5) 可选：写库前先删除将写入的键（彻底去重清洁）
        if dedupe == "delete_then_insert":
            _delete_existing_rows(conn, clean[["symbol", "trade_date"]])

        # 6) 写入 DB（按 mode 控制冲突行为）
        # Adjusting column order to match SQL placement and avoiding 'df.itertuples(name=None)' issue if columns changed
        # Explicitly select columns for insertion
        to_insert = clean[["symbol", "trade_date", "open", "high", "low", "close", "volume", "source"]]
        _insert_rows(conn, to_insert, mode=mode)

        conn.commit()
        print(f"[SUCCESS] Imported rows: {len(clean)} | canonical symbols: {sorted(clean['symbol'].unique().tolist())[:10]} ...")

    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import CSV price data into VERA DB with ambiguity guard + dedupe options.")
    parser.add_argument("path", help="Path to CSV file or directory containing CSVs")
    parser.add_argument("--symbol", "-s", help="Override symbol (single file)")
    parser.add_argument("--source", default="manual_csv", help="Source label")
    parser.add_argument("--mode", choices=["ignore", "upsert", "fail"], default="upsert",
                        help="DB conflict handling: ignore/upsert/fail (default: upsert)")
    parser.add_argument("--dedupe", choices=["keep_last", "keep_first", "delete_then_insert"], default="keep_last",
                        help="Duplicate handling: keep_last/keep_first/delete_then_insert (default: keep_last)")
    parser.add_argument("--asset-type-hint", choices=["INDEX", "STOCK"], default=None,
                        help="Disambiguation hint for CN 6-digit codes (e.g., 000001).")
    args = parser.parse_args()

    if os.path.isdir(args.path):
        files = glob.glob(os.path.join(args.path, "*.csv"))
        print(f"[INFO] Found {len(files)} CSV files.")
        for f in files:
            parse_and_import(
                f,
                symbol_override=None,
                source_label=args.source,
                mode=args.mode,
                dedupe=args.dedupe,
                asset_type_hint=args.asset_type_hint
            )
    elif os.path.isfile(args.path):
        parse_and_import(
            args.path,
            symbol_override=args.symbol,
            source_label=args.source,
            mode=args.mode,
            dedupe=args.dedupe,
            asset_type_hint=args.asset_type_hint
        )
    else:
        raise SystemExit("[ERROR] Path not found.")