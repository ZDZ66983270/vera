
import pandas as pd
import sqlite3
import argparse
import os
from datetime import datetime

DB_PATH = "vera.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def ensure_symbol_map_table(conn: sqlite3.Connection):
    conn.execute("""
    CREATE TABLE IF NOT EXISTS asset_symbol_map (
      canonical_id TEXT NOT NULL,
      symbol TEXT NOT NULL,
      source TEXT,
      priority INTEGER DEFAULT 50,
      is_active INTEGER DEFAULT 1,
      note TEXT,
      created_at TEXT,
      updated_at TEXT,
      PRIMARY KEY (canonical_id, symbol)
    )
    """)
    conn.execute("""
    CREATE INDEX IF NOT EXISTS idx_symbol_map_symbol
    ON asset_symbol_map(symbol, is_active, priority)
    """)
    conn.commit()

def normalize_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    return df

def coerce_int(x, default=0):
    try:
        if pd.isna(x): 
            return default
        return int(float(x))
    except Exception:
        return default

def load_map_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = normalize_cols(df)

    # 支持多种列名
    # 必须：canonical_id, symbol
    rename = {}
    for c in df.columns:
        if c in ("canonical", "canonical_id", "asset", "asset_id"):
            rename[c] = "canonical_id"
        elif c in ("symbol", "alias", "alias_symbol", "ticker", "vendor_symbol"):
            rename[c] = "symbol"
        elif c in ("source", "vendor"):
            rename[c] = "source"
        elif c in ("priority",):
            rename[c] = "priority"
        elif c in ("is_active", "active", "enabled"):
            rename[c] = "is_active"
        elif c in ("note", "remark", "comment"):
            rename[c] = "note"

    df = df.rename(columns=rename)

    if "canonical_id" not in df.columns or "symbol" not in df.columns:
        raise ValueError(f"CSV must include canonical_id and symbol columns. Found: {list(df.columns)}")

    # 标准化
    df["canonical_id"] = df["canonical_id"].astype(str).str.strip().str.upper()
    df["symbol"] = df["symbol"].astype(str).str.strip().str.upper()

    if "source" not in df.columns:
        df["source"] = "manual_map_csv"
    else:
        df["source"] = df["source"].astype(str).str.strip()

    if "priority" not in df.columns:
        df["priority"] = 50
    df["priority"] = df["priority"].apply(lambda x: coerce_int(x, 50))

    if "is_active" not in df.columns:
        df["is_active"] = 1
    df["is_active"] = df["is_active"].apply(lambda x: 1 if coerce_int(x, 1) != 0 else 0)

    if "note" not in df.columns:
        df["note"] = ""
    df["note"] = df["note"].astype(str)

    # 去重（同一 canonical_id + symbol 只保留最后一行）
    df = df.drop_duplicates(subset=["canonical_id", "symbol"], keep="last")

    return df[["canonical_id", "symbol", "source", "priority", "is_active", "note"]]

def upsert_rows(conn: sqlite3.Connection, df: pd.DataFrame, mode: str, dry_run: bool):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur = conn.cursor()

    if mode == "ignore":
        sql = """
        INSERT OR IGNORE INTO asset_symbol_map
        (canonical_id, symbol, source, priority, is_active, note, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
    elif mode == "fail":
        sql = """
        INSERT INTO asset_symbol_map
        (canonical_id, symbol, source, priority, is_active, note, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
    else:
        # upsert
        sql = """
        INSERT INTO asset_symbol_map
        (canonical_id, symbol, source, priority, is_active, note, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(canonical_id, symbol) DO UPDATE SET
            source = excluded.source,
            priority = excluded.priority,
            is_active = excluded.is_active,
            note = excluded.note,
            updated_at = excluded.updated_at
        """

    print(f"[INFO] rows={len(df)} mode={mode} dry_run={dry_run}")
    if dry_run:
        print("[DRY-RUN] Skipped DB write.")
        return

    with conn:
        for _, r in df.iterrows():
            cur.execute(sql, (
                r["canonical_id"], r["symbol"], r["source"],
                int(r["priority"]), int(r["is_active"]), r["note"],
                now, now
            ))

def print_summary(conn: sqlite3.Connection, df: pd.DataFrame, limit: int = 20):
    # 显示：这些 symbol 目前映射到了哪些 canonical（查潜在冲突）
    cur = conn.cursor()
    symbols = df["symbol"].unique().tolist()
    if not symbols:
        return

    placeholders = ",".join(["?"] * min(len(symbols), 500))
    rows = cur.execute(
        f"""
        SELECT symbol, GROUP_CONCAT(canonical_id) AS canonicals, COUNT(*) AS cnt
        FROM asset_symbol_map
        WHERE symbol IN ({placeholders}) AND is_active = 1
        GROUP BY symbol
        HAVING COUNT(*) > 1
        ORDER BY cnt DESC
        LIMIT ?
        """,
        (*symbols[:500], limit)
    ).fetchall()

    if rows:
        print("[WARN] Potential conflicts: one symbol maps to multiple canonical_id (active).")
        for sym, canon, cnt in rows:
            print(f"  - {sym}: {canon} (count={cnt})")
    else:
        print("[INFO] No active symbol->multiple canonical conflicts detected in imported set.")

def main():
    parser = argparse.ArgumentParser(description="Import/maintain asset_symbol_map (alias->canonical).")
    parser.add_argument("csv", help="Path to mapping CSV file")
    parser.add_argument("--mode", choices=["ignore", "upsert", "fail"], default="upsert",
                        help="Conflict handling (default: upsert)")
    parser.add_argument("--dry-run", action="store_true", help="Validate only; no DB write")
    args = parser.parse_args()

    if not os.path.isfile(args.csv):
        print("[ERROR] CSV file not found.")
        return

    try:
        df = load_map_csv(args.csv)
    except Exception as e:
        print(f"[ERROR] Parse mapping CSV failed: {e}")
        return

    conn = get_connection()
    try:
        ensure_symbol_map_table(conn)
        upsert_rows(conn, df, mode=args.mode, dry_run=args.dry_run)
        print_summary(conn, df)
        print("[SUCCESS] asset_symbol_map import complete.")
    except Exception as e:
        print(f"[ERROR] Import failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
