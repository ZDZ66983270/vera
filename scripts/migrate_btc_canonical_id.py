"""
Migrate Bitcoin Canonical ID from CRYPTO:BTC-USD to WORLD:CRYPTO:BTC-USD
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
from db.connection import get_connection

OLD_ID = "CRYPTO:BTC-USD"
NEW_ID = "WORLD:CRYPTO:BTC-USD"

def migrate_btc_canonical_id():
    """Update all references to Bitcoin's canonical ID in the database."""
    conn = get_connection()
    cursor = conn.cursor()
    
    print("=" * 80)
    print("Bitcoin Canonical ID Migration")
    print(f"Migrating from: {OLD_ID}")
    print(f"Migrating to:   {NEW_ID}")
    print("=" * 80)
    
    # Track updates
    updates = {}
    
    # Tables with asset_id column
    asset_id_tables = [
        'assets',
        'financial_history',
        'analysis_snapshot',
        'drawdown_state_history',
        'risk_events',
        'risk_card_snapshot',
        'behavior_flags',
        'asset_sector_map',
        'risk_overlay_snapshot',
        'quality_snapshot',
        'fundamentals_annual',
        'fundamentals_facts',
        'asset_classification',
        'asset_universe'
    ]
    
    print("\n[1] Updating tables with asset_id column...")
    for table in asset_id_tables:
        try:
            cursor.execute(f"UPDATE {table} SET asset_id = ? WHERE asset_id = ?", (NEW_ID, OLD_ID))
            count = cursor.rowcount
            if count > 0:
                updates[table] = count
                print(f"  ✅ {table}: {count} rows updated")
        except sqlite3.OperationalError as e:
            # Table might not exist
            print(f"  ⊘ {table}: skipped ({str(e)})")
    
    # vera_price_cache uses 'symbol' column
    print("\n[2] Updating vera_price_cache...")
    try:
        cursor.execute("UPDATE vera_price_cache SET symbol = ? WHERE symbol = ?", (NEW_ID, OLD_ID))
        count = cursor.rowcount
        if count > 0:
            updates['vera_price_cache'] = count
            print(f"  ✅ vera_price_cache: {count} rows updated")
    except sqlite3.OperationalError as e:
        print(f"  ⊘ vera_price_cache: skipped ({str(e)})")
    
    # asset_symbol_map uses 'canonical_id' column
    print("\n[3] Updating asset_symbol_map...")
    try:
        cursor.execute("UPDATE asset_symbol_map SET canonical_id = ? WHERE canonical_id = ?", (NEW_ID, OLD_ID))
        count = cursor.rowcount
        if count > 0:
            updates['asset_symbol_map'] = count
            print(f"  ✅ asset_symbol_map: {count} rows updated")
    except sqlite3.OperationalError as e:
        print(f"  ⊘ asset_symbol_map: skipped ({str(e)})")
    
    # symbol_alias (if exists)
    print("\n[4] Updating symbol_alias...")
    try:
        cursor.execute("UPDATE symbol_alias SET canonical_id = ? WHERE canonical_id = ?", (NEW_ID, OLD_ID))
        count = cursor.rowcount
        if count > 0:
            updates['symbol_alias'] = count
            print(f"  ✅ symbol_alias: {count} rows updated")
    except sqlite3.OperationalError as e:
        print(f"  ⊘ symbol_alias: skipped ({str(e)})")
    
    # Commit changes
    conn.commit()
    
    # Summary
    print("\n" + "=" * 80)
    print("Migration Summary")
    print("=" * 80)
    
    total_updates = sum(updates.values())
    print(f"\nTotal tables updated: {len(updates)}")
    print(f"Total rows updated: {total_updates}")
    
    if updates:
        print("\nDetailed breakdown:")
        for table, count in sorted(updates.items()):
            print(f"  - {table}: {count} rows")
    
    # Verification
    print("\n" + "=" * 80)
    print("Verification")
    print("=" * 80)
    
    # Check assets table
    cursor.execute("SELECT asset_id, symbol_name, market FROM assets WHERE asset_id = ?", (NEW_ID,))
    row = cursor.fetchone()
    if row:
        print(f"\n✅ Bitcoin asset found with new ID:")
        print(f"   Asset ID: {row[0]}")
        print(f"   Name: {row[1]}")
        print(f"   Market: {row[2]}")
    else:
        print(f"\n⚠️  Warning: Bitcoin asset not found with new ID {NEW_ID}")
    
    # Check for old ID
    cursor.execute("SELECT COUNT(*) FROM assets WHERE asset_id = ?", (OLD_ID,))
    old_count = cursor.fetchone()[0]
    if old_count > 0:
        print(f"\n⚠️  Warning: {old_count} records still using old ID {OLD_ID}")
    else:
        print(f"\n✅ No records found with old ID {OLD_ID}")
    
    conn.close()
    print("\n✅ Migration completed successfully!")

if __name__ == "__main__":
    migrate_btc_canonical_id()
