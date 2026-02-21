
import pandas as pd
from db.connection import get_connection

def check_00998():
    conn = get_connection()
    try:
        # Check latest record for 00998 (Canonical ID might be HK:STOCK:00998 or similar)
        # Search efficiently
        print("--- Finding 00998 ---")
        assets = pd.read_sql("SELECT asset_id, symbol_name FROM assets WHERE asset_id LIKE '%00998%'", conn)
        print(assets)
        
        if not assets.empty:
            aid = assets.iloc[0]['asset_id']
            print(f"\n--- Latest Data for {aid} ---")
            df = pd.read_sql_query("""
                SELECT symbol, trade_date, close, pe, pe_ttm 
                FROM vera_price_cache 
                WHERE symbol = ? 
                ORDER BY trade_date DESC 
                LIMIT 5
            """, conn, params=(aid,))
            print(df)
            
    finally:
        conn.close()

if __name__ == "__main__":
    check_00998()
