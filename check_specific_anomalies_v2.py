import sqlite3
import pandas as pd
import os

DB_PATH = "vera.db"

def check_anomalies_v2():
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print(f"🔍 Checking database anomalies (V2) in: {DB_PATH}\n")

    # 1. Inspect Asset Types
    print("--- 🏷️ Distinct Asset Types ---")
    try:
        cursor.execute("SELECT DISTINCT asset_type FROM assets")
        types = cursor.fetchall()
        print(f"Types found: {[t[0] for t in types]}")
    except:
        pass
    print("\n")

    # 2. List missing financials for 'EQUITY' (assuming this is stock)
    #    Exclude known indices if labeled as equity inappropriately, or just list them.
    #    The user said "exclude ETFs and Indices". 
    print("--- 📉 'EQUITY' Assets without Financial Data ---")
    
    query_equity = "SELECT asset_id, symbol_name FROM assets WHERE asset_type = 'EQUITY'"
    cursor.execute(query_equity)
    all_equities = cursor.fetchall()

    query_fin = "SELECT DISTINCT asset_id FROM financial_history"
    cursor.execute(query_fin)
    fin_ids = set(row[0] for row in cursor.fetchall())

    missing_list = []
    for aid, name in all_equities:
        if aid not in fin_ids:
            missing_list.append((aid, name))

    if missing_list:
        print(f"Found {len(missing_list)} items with type 'EQUITY' missing financials:")
        for aid, name in missing_list:
            print(f"- {aid:<20} ({name})")
    else:
        print("✅ No 'EQUITY' assets are missing financial data.")
    print("\n")

    conn.close()

if __name__ == "__main__":
    check_anomalies_v2()
