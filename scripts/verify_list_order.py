
import sys
import os
sys.path.append(os.getcwd())
import re
from engine.universe_manager import get_universe_assets_v2
from db.connection import get_connection

def verify_new_order():
    # 1. Simulate universe fetching (SQL Order)
    print("Fetching Universe (SQL Order)...")
    universe_df = get_universe_assets_v2()
    # universe_df is a list of dicts
    universe_ids = [row['asset_id'] for row in universe_df]
    
    # 2. Simulate cached fetch
    cached_symbols = ["HK:STOCK:00005", "US:STOCK:AAPL", "EXTRA:OLD:123"]
    
    # 3. Simulate App Logic
    universe_id_set = set(universe_ids)
    extra_ids = [s for s in cached_symbols if s not in universe_id_set]
    all_options = universe_ids + sorted(extra_ids)
    
    print(f"\nTotal Options: {len(all_options)}")
    print("--- Top 10 Assets ---")
    for i, opt in enumerate(all_options[:10]):
        print(f"{i+1}. {opt}")
        
    # Validation
    first = all_options[0]
    if "HK:" in first:
        print("\n[SUCCESS] HK asset is at the top.")
    else:
        print(f"\n[FAILURE] Top asset is {first}, expected HK.")

if __name__ == "__main__":
    verify_new_order()
