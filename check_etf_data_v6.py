import sqlite3
import pandas as pd

def check_etf_data_v6():
    conn = sqlite3.connect('vera.db')
    
    try:
        # 1. Find ETFs by ID pattern
        query_etfs = """
        SELECT asset_id, primary_symbol
        FROM asset_universe
        WHERE asset_id LIKE '%:ETF:%'
        LIMIT 10
        """
        etfs = pd.read_sql(query_etfs, conn)
        print("Sample ETFs found by ID pattern:")
        print(etfs)
        
        if etfs.empty:
            print("No ETFs found with :ETF: pattern.")
            return

        symbols = etfs['primary_symbol'].dropna().unique().tolist()
        
        # 2. Check vera_price_cache
        if symbols:
            placeholders = ','.join('?' for _ in symbols)
            
            # Check PE/PE_TTM
            q_price = f"""
            SELECT symbol, trade_date, pe, pe_ttm
            FROM vera_price_cache
            WHERE symbol IN ({placeholders})
            ORDER BY trade_date DESC
            LIMIT 50
            """
            print(f"\nChecking vera_price_cache for {len(symbols)} symbols: {symbols}")
            prices = pd.read_sql(q_price, conn, params=symbols)
            print(prices)
            
            if not prices.empty:
                print("\nNon-null PE counts in sample:")
                print(prices[['pe', 'pe_ttm']].count())
                print("\nFirst few rows:")
                print(prices.head())
            else:
                 print("No price data found for these symbols.")
                 
        # 3. Double check simple 'QQQ' or 'SPY' if not found by primary_symbol
        # sometimes symbol in cache is just ticker, not canonical
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_etf_data_v6()
