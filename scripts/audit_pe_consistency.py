
import sys
import os
import sqlite3
# Ensure parent dir is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.fetch_fundamentals import fetch_fundamentals
from db.connection import get_connection

def audit_pe(symbol):
    print(f"\n--- Auditing {symbol} ---")
    try:
        fund, bank = fetch_fundamentals(symbol)
        print(f"Details for {symbol}:")
        print(f"  PE TTM (Calc): {fund.pe_ttm}")
        print(f"  EPS TTM: {fund.eps_ttm}")
        print(f"  Price Used: (Infer from PE*EPS) = {fund.pe_ttm * fund.eps_ttm if fund.pe_ttm and fund.eps_ttm else 'N/A'}")
        
        # Verify Price directly from cache
        conn = get_connection()
        cur = conn.cursor()
        
        # Check cache
        cur.execute("SELECT symbol, close, trade_date FROM vera_price_cache WHERE symbol LIKE ? ORDER BY trade_date DESC LIMIT 1", (f"%{symbol.split(':')[-1]}%",))
        row = cur.fetchone()
        if row:
            print(f"  Cache Check ({row[0]}): Close={row[1]} Date={row[2]}")
        else:
            print(f"  Cache Check: Not found for pattern %{symbol.split(':')[-1]}%")
            
        # Check financial history
        cur.execute("SELECT asset_id, eps_ttm, report_date FROM financial_history WHERE asset_id LIKE ? ORDER BY report_date DESC LIMIT 1", (f"%{symbol.split(':')[-1]}%",))
        frow = cur.fetchone()
        if frow:
            print(f"  Financial Check ({frow[0]}): EPS={frow[1]} Date={frow[2]}")
        else:
            print(f"  Financial Check: Not found")
            
        conn.close()
        
    except Exception as e:
        print(f"  Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    audit_pe("HK:STOCK:00005") # HSC
    audit_pe("CN:STOCK:000001") # Ping An
    audit_pe("US:STOCK:TSLA") # Tesla
