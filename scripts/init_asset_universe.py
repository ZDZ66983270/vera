import sqlite3
from db.connection import get_connection

def migrate_to_universe():
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Define core assets to start with
    core_assets = [
        # US Stocks
        ('TSLA', 'yahoo', 'TSLA', 'XLY', 'SPX'),
        ('AAPL', 'yahoo', 'AAPL', 'XLK', 'SPX'),
        ('MSFT', 'yahoo', 'MSFT', 'XLK', 'SPX'),
        ('GOOG', 'yahoo', 'GOOG', 'XLC', 'SPX'),
        ('NVDA', 'yahoo', 'NVDA', 'XLK', 'SPX'),
        ('AMZN', 'yahoo', 'AMZN', 'XLY', 'SPX'),
        
        # HK Stocks
        ('HK:STOCK:00700', 'yahoo', '00700.HK', 'HK:ETF:03033', 'HSI'),
        ('HK:STOCK:00005', 'yahoo', '00005.HK', 'HK:ETF:02800', 'HSI'),
        ('HK:STOCK:01919', 'yahoo', '01919.HK', 'HK:ETF:02800', 'HSI'),
        ('HK:STOCK:00998', 'yahoo', '00998.HK', 'HK:ETF:02800', 'HSI'),
        
        # CN Stocks
        ('CN:STOCK:601919', 'csv_manual', '601919.SS', 'CN:ETF:512800', 'CN:INDEX:000016'),
        ('CN:STOCK:600536', 'csv_manual', '600536.SS', 'CN:ETF:159852', 'CN:INDEX:000905'),
        
        # Indices
        ('SPX', 'yahoo', '^GSPC', None, None),
        ('NDX', 'yahoo', '^NDX', None, None),
        ('DJI', 'yahoo', '^DJI', None, None),
        ('HSI', 'yahoo', '^HSI', None, None),
        ('HSTECH', 'yahoo', '^HSTECH', None, None),
        
        # ETFs
        ('XLK', 'yahoo', 'XLK', None, 'SPX'),
        ('XLE', 'yahoo', 'XLE', None, 'SPX'),
        ('HK:ETF:02800', 'yahoo', '2800.HK', None, 'HSI'),
        ('HK:ETF:03033', 'yahoo', '3033.HK', None, 'HSTECH'),
    ]
    
    # 2. Insert into asset_universe
    print("--- Enrolling core assets into asset_universe ---")
    for aid, source, symbol, sec, mkt in core_assets:
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO asset_universe 
                (asset_id, primary_source, primary_symbol, sector_proxy_id, market_index_id, is_active)
                VALUES (?, ?, ?, ?, ?, 1)
            """, (aid, source, symbol, sec, mkt))
            print(f"Enrolled: {aid}")
        except Exception as e:
            print(f"Failed to enroll {aid}: {e}")
            
    conn.commit()
    conn.close()
    print("Migration to Universe Complete.")

if __name__ == "__main__":
    migrate_to_universe()
