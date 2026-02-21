import sqlite3
import pandas as pd

def diagnose_asset_data():
    conn = sqlite3.connect('vera.db')
    cursor = conn.cursor()
    
    targets = ['600036', '03968', '3968']
    
    print("--- 1. Check Asset Universe ---")
    # Find asset_ids
    found_assets = []
    for t in targets:
        query = f"SELECT * FROM asset_universe WHERE primary_symbol LIKE '%{t}%' OR asset_id LIKE '%{t}%'"
        df = pd.read_sql(query, conn)
        if not df.empty:
            print(f"Found for {t}:")
            print(df)
            found_assets.extend(df['asset_id'].tolist())
            found_assets.extend(df['primary_symbol'].tolist())
        else:
             print(f"No entry found in asset_universe for {t}")

    unique_ids = list(set(found_assets))
    print(f"\nUnique IDs/Symbols found: {unique_ids}")
    
    print("\n--- 2. Check Price Cache ---")
    # Check what symbols actully have data
    for uid in unique_ids:
        # Check exact string
        q = "SELECT symbol, count(*), min(trade_date), max(trade_date) FROM vera_price_cache WHERE symbol = ?"
        res = cursor.execute(q, (uid,)).fetchall()
        print(f"Checking vera_price_cache for exact '{uid}': {res}")
        
        # Check partial
        if ':' in uid:
             # Try parts e.g. CN:STOCK:600036 -> 600036
             parts = uid.split(':')
             if len(parts) > 1:
                 short_sym = parts[-1] 
                 q2 = f"SELECT symbol, count(*), min(trade_date), max(trade_date) FROM vera_price_cache WHERE symbol LIKE '%{short_sym}%'"
                 print(f"Checking vera_price_cache LIKE '%{short_sym}%':")
                 print(pd.read_sql(q2, conn))

    conn.close()

if __name__ == "__main__":
    diagnose_asset_data()
