import sqlite3
import pandas as pd
import os
from datetime import datetime

DB_PATH = "vera.db"

def check_integrity():
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print(f"🔍 Checking database: {DB_PATH}\n")
    
    # 1. List Tables and Row Counts
    print("--- 📊 Table Row Counts ---")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    
    table_stats = []
    for table in tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            table_stats.append((table, count))
        except Exception as e:
            table_stats.append((table, f"Error: {e}"))
            
    # Sort by name
    table_stats.sort(key=lambda x: x[0])
    for table, count in table_stats:
        print(f"{table:<30} : {count:>8}")
    print("\n")

    # 2. Key Tables Logic
    print("--- 🧠 Logical Integrity Checks ---")

    # A. Asset Universe
    asset_ids = set()
    if 'assets' in tables:
        cursor.execute("SELECT asset_id FROM assets")
        asset_ids = set(row[0] for row in cursor.fetchall())
        print(f"✅ Assets in Universe         : {len(asset_ids)}")
    else:
        print("❌ 'assets' table MISSING!")

    # B. Price Cache
    price_symbols = set()
    if 'vera_price_cache' in tables:
        cursor.execute("SELECT DISTINCT symbol FROM vera_price_cache")
        price_symbols = set(row[0] for row in cursor.fetchall())
        print(f"✅ Symbols with Price Data    : {len(price_symbols)}")
        
        # Check coverage
        missing_prices = asset_ids - price_symbols
        if missing_prices:
            print(f"⚠️  {len(missing_prices)} Assets have NO price data: {list(missing_prices)[:5]}...")
        else:
            print("✅ All assets have price data.")

        # Check recency (Are they up to date?)
        cursor.execute("SELECT symbol, MAX(trade_date) FROM vera_price_cache GROUP BY symbol")
        recency_map = dict(cursor.fetchall())
        
        # Find stale data (older than 7 days)
        stale_limit = datetime.now().strftime("%Y-%m-%d") # Rough check, just printing oldest
        # Sort by date
        sorted_dates = sorted(recency_map.items(), key=lambda x: x[1])
        print(f"\n📅 Oldest Data Date found     : {sorted_dates[0][1]} (Symbol: {sorted_dates[0][0]})")
        print(f"📅 Newest Data Date found     : {sorted_dates[-1][1]}")

    # C. Financials
    fin_symbols = set()
    if 'financial_history' in tables:
        cursor.execute("SELECT DISTINCT asset_id FROM financial_history")
        fin_symbols = set(row[0] for row in cursor.fetchall())
        print(f"✅ Symbols with Financials    : {len(fin_symbols)}")

        missing_fin = asset_ids - fin_symbols
        # Filter mostly for stocks (assuming IDs without ':' are stocks or US stocks with 'US:STOCK:')
        # If your IDs use prefixes, adapt logic.
        print(f"ℹ️  Assets/Indices without financials: {len(missing_fin)}")
        if len(missing_fin) > 0 and len(missing_fin) < 20: 
             print(f"    -> {list(missing_fin)}")

    # D. Snapshots (Are they populated?)
    if 'risk_card_snapshot' in tables:
        cursor.execute("SELECT count(DISTINCT symbol) FROM risk_card_snapshot")
        risk_snap_count = cursor.fetchone()[0]
        print(f"✅ Risk Snapshots (Symbols)   : {risk_snap_count}")

    conn.close()

if __name__ == "__main__":
    check_integrity()
