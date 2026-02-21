import sys
import os
import sqlite3

# Add project root to path
sys.path.append(os.getcwd())
try:
    from db.connection import get_connection
except ImportError:
    sys.path.append(os.path.dirname(os.getcwd()))
    from db.connection import get_connection

def delete_assets(target_ids):
    conn = get_connection()
    c = conn.cursor()
    
    deleted_count = 0
    
    # Tables to clean up
    tables = [
        "financial_history",
        "vera_price_cache",
        "market_data_daily",
        "asset_tags",
        "watchlist_items",
        "portfolio_items",
        "assets" # Delete from assets last
    ]
    
    print(f"Deleting assets: {target_ids}")
    
    for asset_id in target_ids:
        print(f"\nProcessing {asset_id}...")
        
        # Check if exists
        exists = c.execute("SELECT 1 FROM assets WHERE asset_id=?", (asset_id,)).fetchone()
        if not exists:
            print(f"  Asset {asset_id} not found, skipping.")
            continue
            
        for table in tables:
            # Handle different column names
            col = "asset_id"
            if table == "vera_price_cache":
                col = "symbol"
            
            try:
                # Check format of delete
                query = f"DELETE FROM {table} WHERE {col} = ?"
                c.execute(query, (asset_id,))
                rows = c.rowcount
                if rows > 0:
                    print(f"  Deleted {rows} rows from {table}")
            except Exception as e:
                print(f"  Error deleting from {table}: {e}")
        
        deleted_count += 1

    conn.commit()
    conn.close()
    print(f"\nSuccessfully deleted {deleted_count} assets.")

if __name__ == "__main__":
    targets = [
        "US:STOCK:BLACK", 
        "US:STOCK:APPL"
    ]
    delete_assets(targets)
