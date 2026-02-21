import argparse
import sqlite3
import pandas as pd
from datetime import datetime
import os

def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_tables(conn: sqlite3.Connection):
    conn.execute("""
    CREATE TABLE IF NOT EXISTS asset_classification (
      asset_id      TEXT NOT NULL,
      scheme        TEXT NOT NULL,
      sector_code   TEXT,
      sector_name   TEXT,
      industry_code TEXT,
      industry_name TEXT,
      as_of_date    TEXT NOT NULL,
      is_active     INTEGER DEFAULT 1,
      PRIMARY KEY(asset_id, scheme, as_of_date)
    );
    """)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS sector_proxy_map (
      scheme           TEXT NOT NULL,
      sector_code      TEXT NOT NULL,
      sector_name      TEXT,
      proxy_etf_id     TEXT NOT NULL,
      market_index_id  TEXT,
      priority         INTEGER DEFAULT 50,
      is_active        INTEGER DEFAULT 1,
      note             TEXT,
      PRIMARY KEY(scheme, sector_code, proxy_etf_id)
    );
    """)
    # Migration: Add column if it doesn't exist
    try:
        conn.execute("ALTER TABLE sector_proxy_map ADD COLUMN market_index_id TEXT")
    except sqlite3.OperationalError:
        pass # Column likely exists

def _norm_str(x):
    return ("" if x is None else str(x)).strip()

def _norm_upper(x):
    return _norm_str(x).upper()

def _norm_date(x) -> str:
    # Accept 'YYYY-MM-DD' or excel-like dates; output 'YYYY-MM-DD'
    if x is None or str(x).strip() == "":
        raise ValueError("as_of_date is required")
    dt = pd.to_datetime(x)
    return dt.strftime("%Y-%m-%d")

def load_and_clean_classification(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [c.strip() for c in df.columns]

    required = ["asset_id","scheme","sector_code","sector_name","industry_code","industry_name","as_of_date","is_active"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"classification csv missing columns: {missing}")

    df["asset_id"] = df["asset_id"].map(_norm_upper)
    df["scheme"] = df["scheme"].map(_norm_upper)
    df["sector_code"] = df["sector_code"].map(_norm_str)
    df["sector_name"] = df["sector_name"].map(_norm_str)
    df["industry_code"] = df["industry_code"].map(_norm_str)
    df["industry_name"] = df["industry_name"].map(_norm_str)
    df["as_of_date"] = df["as_of_date"].map(_norm_date)

    # is_active default
    df["is_active"] = pd.to_numeric(df["is_active"], errors="coerce").fillna(1).astype(int)

    # Drop empty essential fields
    df = df[df["asset_id"] != ""]
    df = df[df["scheme"] != ""]
    return df

def load_and_clean_proxy(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [c.strip() for c in df.columns]

    # Added market_index_id
    required = ["scheme","sector_code","sector_name","proxy_etf_id","market_index_id","priority","is_active","note"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"proxy csv missing columns: {missing}")

    df["scheme"] = df["scheme"].map(_norm_upper)
    df["sector_code"] = df["sector_code"].map(_norm_str)
    df["sector_name"] = df["sector_name"].map(_norm_str)
    df["proxy_etf_id"] = df["proxy_etf_id"].map(_norm_upper)
    df["market_index_id"] = df["market_index_id"].map(_norm_upper)
    df["priority"] = pd.to_numeric(df["priority"], errors="coerce").fillna(50).astype(int)
    df["is_active"] = pd.to_numeric(df["is_active"], errors="coerce").fillna(1).astype(int)
    df["note"] = df["note"].map(_norm_str)

    df = df[df["scheme"] != ""]
    df = df[df["sector_code"] != ""]
    df = df[df["proxy_etf_id"] != ""]
    return df

def upsert_asset_classification(conn: sqlite3.Connection, df: pd.DataFrame, mode: str):
    cur = conn.cursor()
    if mode == "ignore":
        sql = """
        INSERT OR IGNORE INTO asset_classification
        (asset_id, scheme, sector_code, sector_name, industry_code, industry_name, as_of_date, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
    elif mode == "fail":
        sql = """
        INSERT INTO asset_classification
        (asset_id, scheme, sector_code, sector_name, industry_code, industry_name, as_of_date, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
    else:
        sql = """
        INSERT INTO asset_classification
        (asset_id, scheme, sector_code, sector_name, industry_code, industry_name, as_of_date, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(asset_id, scheme, as_of_date) DO UPDATE SET
          sector_code   = excluded.sector_code,
          sector_name   = excluded.sector_name,
          industry_code = excluded.industry_code,
          industry_name = excluded.industry_name,
          is_active     = excluded.is_active
        """

    rows = 0
    for r in df.itertuples(index=False):
        cur.execute(sql, (r.asset_id, r.scheme, r.sector_code, r.sector_name,
                          r.industry_code, r.industry_name, r.as_of_date, int(r.is_active)))
        rows += 1
    return rows

def upsert_sector_proxy_map(conn: sqlite3.Connection, df: pd.DataFrame, mode: str):
    cur = conn.cursor()
    if mode == "ignore":
        sql = """
        INSERT OR IGNORE INTO sector_proxy_map
        (scheme, sector_code, sector_name, proxy_etf_id, market_index_id, priority, is_active, note)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
    elif mode == "fail":
        sql = """
        INSERT INTO sector_proxy_map
        (scheme, sector_code, sector_name, proxy_etf_id, market_index_id, priority, is_active, note)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
    else:
        sql = """
        INSERT INTO sector_proxy_map
        (scheme, sector_code, sector_name, proxy_etf_id, market_index_id, priority, is_active, note)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(scheme, sector_code, proxy_etf_id) DO UPDATE SET
          sector_name      = excluded.sector_name,
          market_index_id  = excluded.market_index_id,
          priority         = excluded.priority,
          is_active        = excluded.is_active,
          note             = excluded.note
        """

    rows = 0
    for r in df.itertuples(index=False):
        cur.execute(sql, (r.scheme, r.sector_code, r.sector_name, r.proxy_etf_id, r.market_index_id,
                          int(r.priority), int(r.is_active), r.note))
        rows += 1
    return rows

def main():
    parser = argparse.ArgumentParser(description="Import classification + sector proxy mappings into VERA DB.")
    parser.add_argument("--db", default="vera.db", help="SQLite DB path (default: vera.db)")
    parser.add_argument("--classification", help="Path to asset_classification.csv")
    parser.add_argument("--proxy", help="Path to sector_proxy_map.csv")
    parser.add_argument("--mode", choices=["upsert","ignore","fail"], default="upsert",
                        help="Conflict mode (default: upsert)")
    args = parser.parse_args()

    conn = connect(args.db)
    try:
        init_tables(conn)

        total_rows = 0

        if args.proxy:
            proxy_df = load_and_clean_proxy(args.proxy)
            n = upsert_sector_proxy_map(conn, proxy_df, args.mode)
            total_rows += n
            print(f"[OK] sector_proxy_map imported rows: {n}, distinct sectors: {proxy_df['sector_code'].nunique()}, distinct ETFs: {proxy_df['proxy_etf_id'].nunique()}")

        if args.classification:
            cls_df = load_and_clean_classification(args.classification)
            n = upsert_asset_classification(conn, cls_df, args.mode)
            total_rows += n
            print(f"[OK] asset_classification imported rows: {n}, distinct assets: {cls_df['asset_id'].nunique()}, distinct sectors: {cls_df['sector_code'].nunique()}")

        conn.commit()
        print(f"[DONE] total processed rows: {total_rows}")

    finally:
        conn.close()

if __name__ == "__main__":
    main()
