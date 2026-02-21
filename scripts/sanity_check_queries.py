
import sqlite3
import os
import sys

sys.path.append(os.getcwd())

def test_queries():
    print("Testing Universe Manager Queries...")
    from engine.universe_manager import get_universe_assets_v2
    try:
        assets = get_universe_assets_v2()
        print(f"✅ `get_universe_assets_v2` returned {len(assets)} assets.")
        if assets:
            print(f"   Sample: {assets[0]}")
    except Exception as e:
        print(f"❌ `get_universe_assets_v2` FAILED: {e}")

    print("\nTesting Asset Resolver Queries...")
    from engine.asset_resolver import resolve_asset, resolve_sector_context
    try:
        # Pick a text existing asset
        from db.connection import get_connection
        conn = get_connection()
        aid = conn.execute("SELECT asset_id FROM assets LIMIT 1").fetchone()
        conn.close()
        
        if aid:
            asset_id = aid[0]
            print(f"   Using asset: {asset_id}")
            info = resolve_asset(asset_id)
            print(f"✅ `resolve_asset` success: {info}")
            
            ctx = resolve_sector_context(asset_id)
            print(f"✅ `resolve_sector_context` success: {ctx}")
        else:
            print("⚠️ No assets in DB to test resolver.")

    except Exception as e:
        print(f"❌ Asset Resolver FAILED: {e}")

if __name__ == "__main__":
    test_queries()
