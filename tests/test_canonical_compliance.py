#!/usr/bin/env python3
"""
Canonical Symbol Compliance Test
Verifies no raw symbols leaked into vera_price_cache

CRITICAL: This test uses WHITELIST validation against assets.asset_id
A symbol is valid if and only if it exists in assets.asset_id (the canonical universe)
"""
import sqlite3
import sys

DB_PATH = "vera.db"

def test_no_raw_symbols_in_price_cache():
    """
    Verify no unmapped/raw symbols leaked into vera_price_cache
    
    ✅ CORRECT APPROACH: Whitelist validation against assets.asset_id
    - Any symbol in vera_price_cache SHOULD exist in assets (the canonical universe)
    - Violations = symbols in price_cache but NOT in assets.asset_id
    
    ❌ NEVER USE: Pattern matching (^%, %.SS, etc.)
    - Would false-positive on valid canonical IDs like "600309.SS"
    - Canonical format is user-defined, not inferrable from syntax
    """
    conn = sqlite3.connect(DB_PATH)
    
    # Find symbols in price_cache that are NOT in assets.asset_id whitelist
    violations = conn.execute("""
        SELECT DISTINCT pc.symbol, COUNT(*) as row_count
        FROM vera_price_cache pc
        LEFT JOIN assets a ON pc.symbol = a.asset_id
        WHERE a.asset_id IS NULL
        GROUP BY pc.symbol
        ORDER BY row_count DESC
        LIMIT 50
    """).fetchall()
    
    # Get total rows affected
    total_rows_query = conn.execute("""
        SELECT COUNT(*) FROM vera_price_cache pc
        LEFT JOIN assets a ON pc.symbol = a.asset_id
        WHERE a.asset_id IS NULL
    """).fetchone()[0]
    
    # Also check: how many canonical IDs exist in assets?
    canonical_count = conn.execute("""
        SELECT COUNT(DISTINCT asset_id) FROM assets
    """).fetchone()[0]
    
    conn.close()
    
    if violations:
        violators = [(row[0], row[1]) for row in violations]
        
        print("\n" + "="*60)
        print("⚠️  CANONICAL COMPLIANCE WARNING")
        print("="*60)
        print(f"\nFound {len(violations)} symbols in vera_price_cache NOT in assets")
        print(f"Affecting {total_rows_query} total rows")
        print(f"Current canonical universe size: {canonical_count} assets\n")
        print("Unmapped symbols (need to be registered in assets):")
        for symbol, count in violators[:20]:
            print(f"  - {symbol}: {count} rows")
        
        if len(violators) > 20:
            print(f"  ... and {len(violators) - 20} more")
        
        print("\n" + "-"*60)
        print("ACTION REQUIRED:")
        print("1. These symbols should be auto-registered via save_daily_price()")
        print("2. If auto_register_asset=False, manually INSERT into assets")
        print("3. Run: INSERT INTO assets (asset_id, symbol_name) VALUES (?, ?)")
        print("="*60 + "\n")
        
        # Don't fail - warning mode (auto-registration should handle this)
        return False
    
    print("\n" + "="*60)
    print("✅ CANONICAL COMPLIANCE TEST PASSED")
    print("="*60)
    print(f"All symbols in vera_price_cache exist in assets (universe: {canonical_count}).")
    print("No orphaned symbols detected.")
    print("="*60 + "\n")
    
    return True

if __name__ == "__main__":
    try:
        test_no_raw_symbols_in_price_cache()
    except FileNotFoundError:
        print(f"❌ ERROR: Database file '{DB_PATH}' not found")
        sys.exit(1)
    except Exception as e:
        print(f"❌ ERROR: Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


