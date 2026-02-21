
import sqlite3
import pandas as pd
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.append(os.getcwd())
try:
    from db.connection import get_connection
except ImportError:
    sys.path.append(os.path.dirname(os.getcwd()))
    from db.connection import get_connection

def recalc_pe_history():
    conn = get_connection()
    c = conn.cursor()
    
    # 1. Get all assets
    assets = c.execute("SELECT asset_id FROM assets WHERE asset_type IN ('EQUITY', 'STOCK')").fetchall()
    
    print(f"Recalculating PE for {len(assets)} assets...")
    
    total_updates = 0
    
    for row in assets:
        asset_id = row[0]
        # Skip if index or other types if check above didn't catch 
        
        # 2. Fetch Financial History (EPS TTM)
        fin_rows = c.execute("""
            SELECT report_date, eps_ttm 
            FROM financial_history 
            WHERE asset_id = ? AND eps_ttm IS NOT NULL 
            ORDER BY report_date ASC
        """, (asset_id,)).fetchall()
        
        if not fin_rows:
            continue
            
        # Build EPS Lookup (Date -> EPS)
        # We need an "As Of" lookup. Since report_date is the period end, 
        # usually data is available later (disclosure date). 
        # But we don't store disclosure date in financial_history yet (only report_date).
        # Assumption: Data becomes effective ~3 months after report_date? 
        # Or simplistic: Use report_date as effective date for TTM?
        # VERA Standard: For backtesting/validation, disclosure date is better, 
        # but for simple display history, report_date is often used as the "data point".
        # Let's align with existing `snapshot_builder` logic (likely uses latest known report).
        
        # Structure: [(date_obj, eps_val), ...]
        eps_timeline = []
        for r_date, eps in fin_rows:
            try:
                dt = datetime.strptime(r_date, "%Y-%m-%d").date()
                eps_timeline.append((dt, float(eps)))
            except:
                pass
                
        if not eps_timeline:
            continue
            
        # 3. Fetch Price Cache
        # We only really need to iterate prices and find match.
        # But querying and updating row-by-row is slow.
        # Better: Load all prices, calc local, batch update? 
        # Or perform Update with a correlated subquery? 
        # SQLite update with subquery from another table is complex.
        
        # Let's load prices into DF
        df_price = pd.read_sql_query(f"SELECT trade_date, close FROM vera_price_cache WHERE symbol='{asset_id}' ORDER BY trade_date", conn)
        
        if df_price.empty:
            continue
            
        df_price['trade_date'] = pd.to_datetime(df_price['trade_date']).dt.date
        
        updates = []
        
        # Iterate prices
        # Optimization: Sort both, single pass?
        # Or simple binary search/lookup for each price.
        
        # Convert EPS timeline to easy lookup
        # Since it's sorted by date, for any trade_date, we want the max(report_date) <= trade_date.
        # Actually usually report is released LATER. 
        # If we use report_date, we have "look ahead" bias if we assume it's available on report_date.
        # But `financial_history` date is `report_date`.
        # Standard generic approach if disclosure missing: 
        # Effective = Report Date + 1 Day (Assuming prompt? No, unrealistic).
        # Or keep it simple: Use Report Date. It's historical reference.
        
        import bisect
        dates = [x[0] for x in eps_timeline]
        vals = [x[1] for x in eps_timeline]
        
        for idx, row in df_price.iterrows():
            t_date = row['trade_date']
            close = row['close']
            
            # Find insertion point to get latest past date
            # bisect_right returns index where t_date would be inserted after existing entries
            i = bisect.bisect_right(dates, t_date)
            
            if i > 0:
                # i-1 is the index of the largest date <= t_date
                eps = vals[i-1]
                if eps != 0:
                    pe = close / eps
                    # Update DB
                    # updates.append((pe, eps, str(t_date), asset_id))
                    # Batch list
                    updates.append((pe, eps, str(t_date)))
        
        if updates:
            # Batch update
            # table: vera_price_cache, keys: symbol, trade_date
            c.executemany(f"""
                UPDATE vera_price_cache 
                SET pe = ?, eps = ? 
                WHERE symbol = '{asset_id}' AND trade_date = ?
            """, updates)
            total_updates += len(updates)
            print(f"  Updated {len(updates)} records for {asset_id}")
            
    conn.commit()
    conn.close()
    print(f"Total PE records recalculated: {total_updates}")

if __name__ == "__main__":
    recalc_pe_history()
