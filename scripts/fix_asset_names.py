import sqlite3
import sys
import os
import re

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db.connection import get_connection
from utils.stock_name_fetcher import get_stock_name

def fix_asset_names():
    conn = get_connection()
    cursor = conn.cursor()
    
    print("Scanning for assets with invalid names...")
    
    # Select all assets to check their names
    cursor.execute("SELECT asset_id, name, market FROM assets")
    rows = cursor.fetchall()
    
    updated_count = 0
    checked_count = 0
    
    for row in rows:
        asset_id = row['asset_id']
        current_name = row['name']
        market = row['market']
        checked_count += 1
        
        if not current_name:
            current_name = ""
            
        # Extract basic symbol
        # HK:STOCK:00700 -> 00700
        parts = asset_id.split(':')
        symbol = parts[-1]
        
        # Criteria for "Bad Name":
        # 1. Contains the full asset_id (e.g. "HK:STOCK:00700")
        # 2. Is exactly the code/symbol (e.g. "00700", "BABA", "03110")
        # 3. Is code + suffix (e.g. "00700.HK", "600519.SH")
        # 4. Is purely numeric (common for HK/CN stocks missing names)
        # 5. Starts with "HK:" (e.g. "HK:00700")
        
        is_bad = False
        
        if current_name == asset_id: is_bad = True
        elif current_name == symbol: is_bad = True
        elif current_name.upper() == f"{symbol}.HK": is_bad = True
        elif current_name.upper() == f"{symbol}.SH": is_bad = True
        elif current_name.upper() == f"{symbol}.SZ": is_bad = True
        elif current_name.upper().startswith("HK:"): is_bad = True
        elif re.match(r'^\d+$', current_name): is_bad = True # Pure digits like "03110"
        
        # Additional check: If name is same as symbol but symbol is purely alpha (US stocks), 
        # it might be acceptable (e.g. AAPL name is AAPL?), 
        # BUT ideally we want "Apple Inc." or similar. 
        # For now, let's focus on CN/HK which are most problematic. 
        # US stocks often have "AAPL" as name which is passable, but "00700" is bad.
        if market == 'US' and current_name == symbol:
             # Let's try to fetch a better name anyway
             is_bad = True

        if is_bad:
            # Construct query symbol for fetcher
            query_symbol = symbol
            if market == 'HK':
                if not symbol.endswith('.HK'):
                    query_symbol = f"{symbol}.HK"
            elif market == 'CN':
                # Attempt to guess suffix if missing, or use id if it has info
                # Usually CN asset_id is like CN:STOCK:600519
                # If symbol is just 600519, we might need suffix for smartbox?
                # stock_name_fetcher handles 6 digit codes fairly well, 
                # but explicit suffix helps (SH/SZ). 
                # Simple logic based on first digit:
                if len(symbol) == 6:
                    if symbol.startswith('6'): query_symbol = f"{symbol}.SH"
                    elif symbol.startswith(('0', '3')): query_symbol = f"{symbol}.SZ"
                    # 5/1 for ETFs usually handled too
            
            print(f"Fixing name for {asset_id} (Current: {current_name}) -> Query: {query_symbol}")
            
            new_name = get_stock_name(query_symbol)
            
            # Validation: Did we get a better name?
            # If fetcher returned the same symbol back, it failed or that's the only name it found.
            # We also check if new_name is still just digits.
            
            fetched_is_valid = True
            if new_name == query_symbol: fetched_is_valid = False
            if new_name == symbol: fetched_is_valid = False
            
            if fetched_is_valid:
                # If we got "Tencent", that is strictly better than "00700"
                if new_name != current_name:
                    print(f"  -> Found: {new_name}")
                    cursor.execute("UPDATE assets SET name = ? WHERE asset_id = ?", (new_name, asset_id))
                    updated_count += 1
                else:
                    print("  -> Found same name, skipping update.")
            else:
                print(f"  -> Could not resolve new name (Got: {new_name})")

    conn.commit()
    conn.close()
    print(f"Finished. Scanned {checked_count} assets. Updated {updated_count} assets.")

if __name__ == "__main__":
    fix_asset_names()
