
import pandas as pd
from db.connection import get_connection

def check_latest_pe_data():
    conn = get_connection()
    try:
        # 1. Find the asset matching the screenshot (Price ~14, PE ~5.2)
        print("--- Searching for asset with Price ~159.9 (Screenshot 1) and ~14 (Screenshot 2) ---")
        
        # Search for Price ~159.9
        query_high = """
        SELECT symbol, trade_date, close, pe, pe_ttm 
        FROM vera_price_cache 
        WHERE trade_date >= '2026-01-01'
          AND close BETWEEN 158 AND 162
        LIMIT 5
        """
        print("\nCandidates for Price ~159.9:")
        print(pd.read_sql_query(query_high, conn))

        # Search for Price ~14 and PE ~5.2
        query_low = """
        SELECT symbol, trade_date, close, pe, pe_ttm 
        FROM vera_price_cache 
        WHERE trade_date >= '2026-01-01'
          AND close BETWEEN 13 AND 15
          AND (pe BETWEEN 5 AND 6 OR pe_ttm BETWEEN 5 AND 6)
        LIMIT 5
        """
        df_match = pd.read_sql_query(query_low, conn)
        print("\nCandidates for Price ~14, PE ~5.2:")
        print(df_match)
        
        target_symbol = None
        if not df_match.empty:
            target_symbol = df_match.iloc[0]['symbol']
            print(f"\nLocked on candidate: {target_symbol}")
        
        if target_symbol:
            # 2. Dump recent history for this symbol
            print(f"\n--- Recent Data for {target_symbol} ---")
            query_hist = """
            SELECT symbol, trade_date, close, pe, pe_ttm 
            FROM vera_price_cache 
            WHERE symbol = ?
            ORDER BY trade_date DESC
            LIMIT 20
            """
            df_hist = pd.read_sql_query(query_hist, conn, params=(target_symbol,))
            print(df_hist)
            
            # 3. Check for specific anomalies (Negative PE, huge jumps)
            print("\n--- Checking for anomalies (Negative PE) ---")
            query_anomaly = """
            SELECT symbol, trade_date, close, pe, pe_ttm 
            FROM vera_price_cache 
            WHERE symbol = ? AND (pe < 0 OR pe_ttm < 0)
            ORDER BY trade_date DESC
            LIMIT 10
            """
            df_anomaly = pd.read_sql_query(query_anomaly, conn, params=(target_symbol,))
            print(df_anomaly)

    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_latest_pe_data()
