import sqlite3
import pandas as pd
import os

DB_PATH = "vera.db"

def check_anomalies():
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print(f"🔍 Checking database anomalies in: {DB_PATH}\n")

    # 1. List missing financials for STOCKS only
    print("--- 📉 Stocks (excluding ETFs/Indices) without Financial Data ---")
    
    # Get all asset_ids that are Stocks
    # Assuming asset_type or asset_role helps distinguish. Based on previous schema: column 5 is asset_type
    query_stocks = "SELECT asset_id, symbol_name FROM assets WHERE asset_type = 'STOCK'"
    try:
        cursor.execute(query_stocks)
        all_stocks = cursor.fetchall() # list of (id, name)
    except Exception as e:
        print(f"Error querying assets: {e}")
        conn.close()
        return

    # Get asset_ids present in financial_history
    query_fin = "SELECT DISTINCT asset_id FROM financial_history"
    try:
        cursor.execute(query_fin)
        fin_ids = set(row[0] for row in cursor.fetchall())
    except Exception as e:
        print(f"Error querying financial_history: {e}")
        fin_ids = set()

    missing_stocks = []
    for aid, name in all_stocks:
        if aid not in fin_ids:
            missing_stocks.append((aid, name))

    if missing_stocks:
        print(f"Found {len(missing_stocks)} stocks missing financials:")
        for aid, name in missing_stocks:
            print(f"- {aid:<20} ({name})")
    else:
        print("✅ No stocks are missing financial data.")
    print("\n")

    # 2. Check specific assets in watchlist (assets table)
    print("--- 🎯 Check Specific Assets in Watchlist ---")
    targets = ["HK:STOCK:01211", "CN:STOCK:000001", "CN:STOCK:000300"]
    
    for target in targets:
        cursor.execute("SELECT asset_id, symbol_name, asset_type FROM assets WHERE asset_id = ?", (target,))
        row = cursor.fetchone()
        if row:
            print(f"✅ FOUND: {target}")
            print(f"   Details: Name='{row[1]}', Type='{row[2]}'")
        else:
            print(f"❌ NOT FOUND: {target}")

    conn.close()

if __name__ == "__main__":
    check_anomalies()
