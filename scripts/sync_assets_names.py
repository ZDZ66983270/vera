import sqlite3
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.stock_name_fetcher import get_stock_name
from db.connection import get_connection

def sync_assets():
    print("Starting asset name sync...")
    conn = get_connection()
    try:
        # 1. Get all symbols from price cache
        cached_rows = conn.execute("SELECT DISTINCT symbol FROM vera_price_cache").fetchall()
        cached_symbols = {r[0] for r in cached_rows}
        print(f"Found {len(cached_symbols)} symbols in cache.")

        # 2. Get existing assets
        asset_rows = conn.execute("SELECT id FROM assets").fetchall()
        existing_assets = {r[0] for r in asset_rows}
        print(f"Found {len(existing_assets)} existing assets.")

        # 3. Identify missing
        missing = cached_symbols - existing_assets
        print(f"Missing {len(missing)} assets in assets table.")

        if not missing:
            print("No missing assets.")
            return

        # 4. Fetch and insert
        new_records = []
        for sym in missing:
            # Skip verify special prefixes if needed, but get_stock_name handles raw usually
            name = get_stock_name(sym)
            if name == sym:
                # If fetch failed, try adding suffix if it looks like CN/HK
                if sym.isdigit() and len(sym) == 6:
                     # Try .SS first (common for main board)
                     name = get_stock_name(f"{sym}.SS")
                     if name == f"{sym}.SS":
                         name = get_stock_name(f"{sym}.SZ")
                elif sym.isdigit() and len(sym) == 5:
                     name = get_stock_name(f"{sym}.HK")

            # Determine region/sector based on symbol format
            market = "US"
            search_sym = sym
            if sym.startswith("CN:STOCK:"):
                # Strip prefix for name search
                raw_code = sym.split(":")[-1]
                search_sym = raw_code
                market = "CN"
                # Try getting name with suffixes
                name = get_stock_name(f"{raw_code}.SS")
                if name == f"{raw_code}.SS":
                     name = get_stock_name(f"{raw_code}.SZ")
            elif ".HK" in sym: 
                market = "HK"
            elif ".SS" in sym or ".SZ" in sym: 
                market = "CN"
            else:
                 # Check if it's potentially CN code without suffix
                 name_check = get_stock_name(sym)
                 if name_check == sym and sym.isdigit() and len(sym) == 6:
                     # Try .SS/.SZ
                     name = get_stock_name(f"{sym}.SS")
                     if name == f"{sym}.SS":
                         name = get_stock_name(f"{sym}.SZ")
                     market = "CN"
                 else:
                     name = name_check

            # Simple insert
            print(f"  Adding {sym} -> {name} ({market})")
            new_records.append((sym, name, market, "Unknown", "2025-01-01", "EQUITY"))

        if new_records:
             conn.executemany("""
                INSERT OR IGNORE INTO assets (asset_id, symbol_name, market, industry, created_at, asset_type)
                VALUES (?, ?, ?, ?, ?, ?)
             """, new_records)
             conn.commit()
             print(f"Inserted {len(new_records)} records.")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    sync_assets()
