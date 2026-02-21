import sqlite3
import os

DB_PATH = "/Users/zhangzy/My Docs/Privates/22-AI编程/VERA/vera.db"

def run_cleanup():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    print("--- 1. Cleaning asset_symbol_map Redundancy ---")
    # Remove nested prefixes like HK:INDEX:HK:INDEX:...
    cur.execute("DELETE FROM asset_symbol_map WHERE canonical_id LIKE '%:%:%:%' OR symbol LIKE '%:%:%:%'")
    print(f"Removed {cur.rowcount} redundant records from asset_symbol_map.")
    
    print("\n--- 2. Cleaning vera_price_cache Duplicates (STOCK vs ETF) ---")
    # Identify overlaps by splitting ID parts and comparing
    # Standard format is MARKET:TYPE:CODE
    cur.execute("SELECT symbol FROM vera_price_cache GROUP BY symbol")
    all_symbols = [r[0] for r in cur.fetchall()]
    
    # Map of code -> list of full symbols
    code_map = {}
    for sym in all_symbols:
        parts = sym.split(":")
        if len(parts) == 3:
            code = parts[2]
            if code not in code_map: code_map[code] = []
            code_map[code].append(sym)
            
    for code, syms in code_map.items():
        if len(syms) > 1:
            print(f"Overlap found for {code}: {syms}")
            # If we have both STOCK and ETF for the same code, we keep ETF (standard for these identifiers)
            if any(":ETF:" in s for s in syms) and any(":STOCK:" in s for s in syms):
                stock_sym = next(s for s in syms if ":STOCK:" in s)
                cur.execute("DELETE FROM vera_price_cache WHERE symbol = ?", (stock_sym,))
                print(f"Removed redundant STOCK entry for {code}: {stock_sym}")

    print("\n--- 3. Merging BTC and BTC-USD ---")
    # Target: US:STOCK:BTC-USD
    target_id = "US:STOCK:BTC-USD"
    # A. Update Symbol Map
    cur.execute("UPDATE asset_symbol_map SET canonical_id = ? WHERE canonical_id = 'US:STOCK:BTC' OR symbol = 'BTC'", (target_id,))
    # B. Consolidate Price Cache
    # First, move all raw 'BTC-USD' and 'US:STOCK:BTC' to 'US:STOCK:BTC-USD'
    # Use INSERT OR IGNORE to avoid primary key conflicts
    cur.execute("""
        INSERT OR IGNORE INTO vera_price_cache (symbol, trade_date, open, high, low, close, volume, source)
        SELECT ?, trade_date, open, high, low, close, volume, source
        FROM vera_price_cache
        WHERE symbol IN ('BTC-USD', 'US:STOCK:BTC')
    """, (target_id,))
    # Delete the old ones
    cur.execute("DELETE FROM vera_price_cache WHERE symbol IN ('BTC-USD', 'US:STOCK:BTC')")
    # C. Cleanup assets
    cur.execute("DELETE FROM assets WHERE asset_id = 'US:STOCK:BTC'")
    cur.execute("UPDATE assets SET symbol_name = 'BTC (Bitcoin)' WHERE asset_id = ?", (target_id,))
    
    conn.commit()
    conn.close()
    print("\n✅ Cleanup Complete.")

if __name__ == "__main__":
    run_cleanup()
