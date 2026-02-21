
import sqlite3
from datetime import datetime
import os

DB_PATH = "vera.db"

ETF_SETS = [
    # -------- Market / Macro Benchmarks (INDEX_PROXY) --------
    ("SPY",  "SPDR S&P 500 ETF Trust",                 "US", "Market Benchmark", "ETF", "INDEX_PROXY"),
    ("QQQ",  "Invesco QQQ Trust",                      "US", "Market Benchmark", "ETF", "INDEX_PROXY"),
    ("DIA",  "SPDR Dow Jones Industrial Average ETF",  "US", "Market Benchmark", "ETF", "INDEX_PROXY"),
    ("ACWI", "iShares MSCI ACWI ETF",                  "GLOBAL", "Market Benchmark", "ETF", "INDEX_PROXY"),
    ("EEM",  "iShares MSCI Emerging Markets ETF",      "GLOBAL", "Market Benchmark", "ETF", "INDEX_PROXY"),
    ("EFA",  "iShares MSCI EAFE ETF",                  "GLOBAL", "Market Benchmark", "ETF", "INDEX_PROXY"),

    # -------- GICS Sector (SECTOR_PROXY) : US SPDR Select Sector --------
    ("XLK",  "Technology Select Sector SPDR Fund",     "US", "Technology",        "ETF", "SECTOR_PROXY"),
    ("XLF",  "Financial Select Sector SPDR Fund",      "US", "Financials",        "ETF", "SECTOR_PROXY"),
    ("XLV",  "Health Care Select Sector SPDR Fund",    "US", "Health Care",       "ETF", "SECTOR_PROXY"),
    ("XLP",  "Consumer Staples Select Sector SPDR",    "US", "Consumer Staples",  "ETF", "SECTOR_PROXY"),
    ("XLY",  "Consumer Discretionary Select Sector",   "US", "Consumer Discretionary", "ETF", "SECTOR_PROXY"),
    ("XLI",  "Industrial Select Sector SPDR Fund",     "US", "Industrials",       "ETF", "SECTOR_PROXY"),
    ("XLE",  "Energy Select Sector SPDR Fund",         "US", "Energy",            "ETF", "SECTOR_PROXY"),
    ("XLB",  "Materials Select Sector SPDR Fund",      "US", "Materials",         "ETF", "SECTOR_PROXY"),
    ("XLU",  "Utilities Select Sector SPDR Fund",      "US", "Utilities",         "ETF", "SECTOR_PROXY"),
    ("XLRE", "Real Estate Select Sector SPDR Fund",    "US", "Real Estate",       "ETF", "SECTOR_PROXY"),
    ("XLC",  "Communication Services Select Sector",   "US", "Communication Services", "ETF", "SECTOR_PROXY"),

    # -------- Style / Factor (STYLE_PROXY) --------
    ("VUG",  "Vanguard Growth ETF",                    "US", "Style",             "ETF", "STYLE_PROXY"),
    ("VTV",  "Vanguard Value ETF",                     "US", "Style",             "ETF", "STYLE_PROXY"),
    ("VYM",  "Vanguard High Dividend Yield ETF",       "US", "Style",             "ETF", "STYLE_PROXY"),
    ("USMV", "iShares MSCI USA Min Vol Factor ETF",    "US", "Style",             "ETF", "STYLE_PROXY"),
    ("IWM",  "iShares Russell 2000 ETF",               "US", "Style",             "ETF", "STYLE_PROXY"),
    ("QUAL", "iShares MSCI USA Quality Factor ETF",    "US", "Style",             "ETF", "STYLE_PROXY"),

    # -------- Defensive / Risk-Contrast (DEFENSIVE_PROXY) --------
    ("TLT",  "iShares 20+ Year Treasury Bond ETF",     "US", "Defensive",         "ETF", "DEFENSIVE_PROXY"),
    ("SHY",  "iShares 1-3 Year Treasury Bond ETF",     "US", "Defensive",         "ETF", "DEFENSIVE_PROXY"),
    ("TIP",  "iShares TIPS Bond ETF",                  "US", "Defensive",         "ETF", "DEFENSIVE_PROXY"),
    ("GLD",  "SPDR Gold Shares",                       "US", "Defensive",         "ETF", "DEFENSIVE_PROXY"),
    ("DBC",  "Invesco DB Commodity Index Tracking",    "US", "Defensive",         "ETF", "DEFENSIVE_PROXY"),
    # 波动率类谨慎，可先留空：("VIXY", "ProShares VIX Short-Term Futures ETF", "US", "Defensive", "ETF", "DEFENSIVE_PROXY"),
]


def ensure_columns(conn: sqlite3.Connection):
    """
    兼容你当前 assets 表可能只有 (asset_id, symbol_name, market, industry) 的情况：
    - 尝试新增 asset_type / asset_role / updated_at 字段
    """
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(assets)")
    cols = {r[1] for r in cur.fetchall()}

    alter_statements = []
    if "asset_type" not in cols:
        alter_statements.append("ALTER TABLE assets ADD COLUMN asset_type TEXT")
    if "asset_role" not in cols: # Note: schema might use index_role, checking consistency...
        # Wait, previous snapshot_builder used index_role. Let's stick to asset_role as per this script or unify?
        # The script says asset_role. I should probably respect the script or fix schema. 
        # But snapshot_builder used `index_role` in previously viewed code.
        # Let's add asset_role as requested by THIS script. It can coexist or replace.
        alter_statements.append("ALTER TABLE assets ADD COLUMN asset_role TEXT")
    if "updated_at" not in cols:
        alter_statements.append("ALTER TABLE assets ADD COLUMN updated_at TEXT")

    for sql in alter_statements:
        try:
            cur.execute(sql)
            print(f"[INFO] Executed: {sql}")
        except Exception as e:
            print(f"[WARN] Skip alter: {sql} ({e})")

    conn.commit()


def upsert_assets(conn: sqlite3.Connection):
    """
    插入或更新 assets。兼容 assets 主键是 asset_id 的 ON CONFLICT。
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur = conn.cursor()

    # 尽量使用 asset_type/asset_role（若列不存在，上一步会补齐）
    sql = """
    INSERT INTO assets (asset_id, symbol_name, market, industry, asset_type, asset_role, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(asset_id) DO UPDATE SET
        symbol_name = excluded.symbol_name,
        market      = excluded.market,
        industry    = excluded.industry,
        asset_type  = excluded.asset_type,
        asset_role  = excluded.asset_role,
        updated_at  = excluded.updated_at
    """
    for asset_id, name, market, industry, asset_type, asset_role in ETF_SETS:
        cur.execute(sql, (asset_id, name, market, industry, asset_type, asset_role, now))

    conn.commit()


def main():
    if not os.path.exists(DB_PATH):
        print(f"[WARN] DB not found at {DB_PATH}, creating empty one if connection allows, but schema might be missing.")
    
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        ensure_columns(conn)
        upsert_assets(conn)
        print(f"[OK] Insert/Update {len(ETF_SETS)} ETFs into assets table.")
        print("[INFO] You can now treat these as sector/style/defensive proxies in VERA.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
