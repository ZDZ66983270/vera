import sqlite3
import os

DB_PATH = "/Users/zhangzy/My Docs/Privates/22-AI编程/VERA/vera.db"

def fix_data():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    print("--- 1. Cleaning asset_universe ID Redundancy ---")
    # Clean nested prefixes like HK:ETF:HK:ETF:...
    cur.execute("""
        UPDATE asset_universe 
        SET sector_proxy_id = REPLACE(REPLACE(sector_proxy_id, 'HK:ETF:HK:ETF:', 'HK:ETF:'), 'HK:INDEX:HK:INDEX:', 'HK:INDEX:'),
            market_index_id = REPLACE(REPLACE(market_index_id, 'HK:ETF:HK:ETF:', 'HK:ETF:'), 'HK:INDEX:HK:INDEX:', 'HK:INDEX:')
        WHERE sector_proxy_id LIKE '%:%:%:%' OR market_index_id LIKE '%:%:%:%'
    """)
    print(f"Updated {cur.rowcount} records in asset_universe.")

    cur.execute("""
        UPDATE asset_classification
        SET asset_id = REPLACE(REPLACE(asset_id, 'HK:ETF:HK:ETF:', 'HK:ETF:'), 'HK:INDEX:HK:INDEX:', 'HK:INDEX:')
        WHERE asset_id LIKE '%:%:%:%'
    """)
    print(f"Updated {cur.rowcount} records in asset_classification.")

    print("\n--- 2. Calibrating 00998.HK Valuation ---")
    # CITIC Bank Total Shares: ~48.93B
    total_shares = 48934844000
    
    # Get latest net income (TTM)
    # Based on DB check, report_date 2024-12-31 net_income is 68576000000.0
    cur.execute("SELECT net_income_ttm FROM financial_fundamentals WHERE asset_id = 'HK:STOCK:00998' ORDER BY as_of_date DESC LIMIT 1")
    row = cur.fetchone()
    if row and row[0]:
        net_income = row[0]
        eps = net_income / total_shares
        print(f"Calculated Correct EPS: {eps:.4f} (Net Income: {net_income:.2f} / Total Shares: {total_shares})")
        
        # Update Price Cache for 00998
        # Get latest price
        cur.execute("SELECT trade_date, close FROM vera_price_cache WHERE symbol = 'HK:STOCK:00998' ORDER BY trade_date DESC")
        rows = cur.fetchall()
        for trade_date, close_price in rows:
            new_pe = close_price / eps
            new_market_cap = close_price * total_shares
            cur.execute("""
                UPDATE vera_price_cache 
                SET pe = ?, eps = ?, market_cap = ?, source = 'System_Correction'
                WHERE symbol = 'HK:STOCK:00998' AND trade_date = ?
            """, (new_pe, eps, new_market_cap, trade_date))
        print(f"Updated {len(rows)} price records for 00998.HK. Latest PE: {rows[0][1]/eps:.2f}")

    conn.commit()
    conn.close()
    print("\n✅ Correction Complete.")

if __name__ == "__main__":
    fix_data()
