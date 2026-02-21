import sqlite3
import pandas as pd

def check_etf_data_v5():
    conn = sqlite3.connect('vera.db')
    cursor = conn.cursor()
    
    try:
        # 1. Inspect asset_classification contents
        print("Sample asset_classification data:")
        query_sample = "SELECT * FROM asset_classification LIMIT 10"
        print(pd.read_sql(query_sample, conn))
        
        # 2. Try to find 'ETF' in sector_name or industry_name
        query_etfs = """
        SELECT a.asset_id, a.primary_symbol as symbol, c.sector_name, c.industry_name
        FROM asset_universe a
        JOIN asset_classification c ON a.asset_id = c.asset_id
        WHERE c.sector_name LIKE '%ETF%' 
           OR c.industry_name LIKE '%ETF%'
           OR c.industry_name IN ('Exchange Traded Fund', 'Fund')
        LIMIT 10
        """
        etfs = pd.read_sql(query_etfs, conn)
        print("\nPossible ETFs found:")
        print(etfs)
        
        if etfs.empty:
            print("No ETFs found by name search.")
            # Try to infer from symbol? e.g. 'US:...' usually stocks but maybe check one known ETF like SPY or QQQ?
            # Or check US/105.QQQ (canonical id)
            query_qqq = "SELECT * FROM asset_universe WHERE primary_symbol LIKE '%QQQ%' OR asset_id LIKE '%QQQ%'"
            print("\nChecking for QQQ:")
            print(pd.read_sql(query_qqq, conn))
            
            return

        symbols = etfs['symbol'].dropna().unique().tolist()
        asset_ids = etfs['asset_id'].unique().tolist()
        
        # 3. Check vera_price_cache (uses symbol)
        # Note: primary_symbol might differ from vera_price_cache symbol, but usually close.
        # Let's try matching both primary_symbol and maybe a cleaner version.
        
        placeholders = ','.join('?' for _ in symbols)
        if symbols:
            q_price = f"""
            SELECT symbol, trade_date, close, pe, pe_ttm
            FROM vera_price_cache
            WHERE symbol IN ({placeholders})
            AND trade_date > '2025-01-01'
            ORDER BY trade_date DESC
            LIMIT 20
            """
            print("\nChecking vera_price_cache for PE/PE_TTM:")
            prices = pd.read_sql(q_price, conn, params=symbols)
            print(prices)
            
            if not prices.empty:
                print("Non-null counts in price cache sample:")
                print(prices[['pe', 'pe_ttm']].count())
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_etf_data_v5()
