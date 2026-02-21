import sys
import os
import sqlite3

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

try:
    from db.connection import get_connection
except ImportError:
    sys.path.append(os.getcwd())
    from db.connection import get_connection

def update_btc_id():
    print("Updating BTC Canonical ID...")
    
    OLD_ID = "WORLD:CRYPTO:BTC-USD"
    NEW_ID = "US:CRYPTO:BTC-USD"
    
    conn = get_connection()
    cursor = conn.cursor()
    
    tables_to_check = [
        "assets",
        "asset_universe",
        "asset_classification",
        "financial_history",
        "quality_snapshot",
        "risk_assessment_history",
        "risk_events",
        "asset_tags"
    ]
    
    # 1. Check if OLD_ID exists in assets
    cursor.execute("SELECT 1 FROM assets WHERE asset_id = ?", (OLD_ID,))
    if not cursor.fetchone():
        print(f"Warning: {OLD_ID} not found in assets. Checking if already updated.")
        cursor.execute("SELECT 1 FROM assets WHERE asset_id = ?", (NEW_ID,))
        if cursor.fetchone():
            print(f"Success: {NEW_ID} already exists.")
        else:
            print(f"Error: Neither {OLD_ID} nor {NEW_ID} found.")
        conn.close()
        return

    print(f"Renaming {OLD_ID} -> {NEW_ID}")
    
    # 2. Update all referencing tables (with ON CONFLICT handling if needed, but usually ID update cascades if foreign keys set, but sqlite support varies. Manual update safest)
    
    # Start transaction
    try:
        cursor.execute("BEGIN TRANSACTION")
        
        # Disable FK checks temporarily to avoid constraint errors during swap
        cursor.execute("PRAGMA foreign_keys = OFF")
        
        # Check if NEW_ID already exists (conflict) - if so, we might need to merge or delete old.
        # Assuming NEW_ID doesn't exist yet as primary asset.
        
        # ASSETS Table
        cursor.execute("UPDATE assets SET asset_id = ?, market = 'US' WHERE asset_id = ?", (NEW_ID, OLD_ID))
        print(f"Updated assets: {cursor.rowcount} rows")
        
        # ASSET_UNIVERSE
        cursor.execute("UPDATE asset_universe SET asset_id = ? WHERE asset_id = ?", (NEW_ID, OLD_ID))
        print(f"Updated asset_universe: {cursor.rowcount} rows")
        
        # ASSET_SYMBOL_MAP
        # Special case: The canonical_id column needs update
        cursor.execute("UPDATE asset_symbol_map SET canonical_id = ? WHERE canonical_id = ?", (NEW_ID, OLD_ID))
        print(f"Updated asset_symbol_map: {cursor.rowcount} rows")

        # OTHER TABLES
        other_tables = [
            "asset_classification", 
            "financial_history", 
            "quality_snapshot",
            "risk_assessment_history",
            "risk_events",
            "asset_tags"
            # Note: vera_price_cache uses 'symbol' not asset_id directly usually, but check schema
            # asset_symbol_map links canonical to symbol. Price cache uses symbol.
            # If vera_price_cache uses canonical_id in 'symbol' col (some implementations do), checking:
        ]
        
        for tbl in other_tables:
            try:
                cursor.execute(f"UPDATE {tbl} SET asset_id = ? WHERE asset_id = ?", (NEW_ID, OLD_ID))
                print(f"Updated {tbl}: {cursor.rowcount} rows")
            except Exception as e:
                print(f"Skipping {tbl} (might not exist or have asset_id): {e}")

        # VERA_PRICE_CACHE
        # Check if it uses canonical IDs
        cursor.execute("SELECT symbol FROM vera_price_cache WHERE symbol = ? LIMIT 1", (OLD_ID,))
        if cursor.fetchone():
             cursor.execute("UPDATE vera_price_cache SET symbol = ? WHERE symbol = ?", (NEW_ID, OLD_ID))
             print(f"Updated vera_price_cache (canonical): {cursor.rowcount} rows")
             
        cursor.execute("PRAGMA foreign_keys = ON")
        conn.commit()
        print("Update complete successfully.")
        
    except Exception as e:
        conn.rollback()
        print(f"FAILED: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    update_btc_id()
