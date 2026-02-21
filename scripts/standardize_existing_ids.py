#!/usr/bin/env python3
"""
Standardize existing non-canonical asset IDs in the database.
Converts raw symbols like '3110' or '600000' to canonical format like 'HK:ETF:03110' or 'CN:STOCK:600000'.
"""

import sqlite3
from db.connection import get_connection
from utils.canonical_resolver import resolve_canonical_symbol

def standardize_existing_ids():
    print("--- Starting ID Standardization Migration ---")
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Fetch all assets that don't follow the canonical pattern
        cursor.execute("""
            SELECT asset_id, market, asset_type 
            FROM assets 
            WHERE asset_id NOT LIKE '%:%:%'
        """)
        non_canonical = cursor.fetchall()
        
        if not non_canonical:
            print("✅ No non-canonical IDs found. Database is clean.")
            return
        
        print(f"Found {len(non_canonical)} non-canonical asset IDs to standardize.")
        
        standardized_count = 0
        error_count = 0
        
        for old_id, market, asset_type in non_canonical:
            try:
                # Generate the canonical ID
                new_id = resolve_canonical_symbol(
                    conn, 
                    old_id, 
                    asset_type_hint=asset_type, 
                    market_hint=market
                )
                
                # Skip if already canonical
                if old_id == new_id:
                    continue
                
                print(f"  [MIGRATE] {old_id} -> {new_id}")
                
                # Update assets table
                cursor.execute("""
                    UPDATE assets SET asset_id = ? WHERE asset_id = ?
                """, (new_id, old_id))
                
                # Update asset_universe table
                cursor.execute("""
                    UPDATE asset_universe SET asset_id = ? WHERE asset_id = ?
                """, (new_id, old_id))
                
                # Update asset_classification table
                cursor.execute("""
                    UPDATE asset_classification SET asset_id = ? WHERE asset_id = ?
                """, (new_id, old_id))
                
                # Update asset_symbol_map canonical_id references
                cursor.execute("""
                    UPDATE asset_symbol_map SET canonical_id = ? WHERE canonical_id = ?
                """, (new_id, old_id))
                
                # Add the old ID as a symbol mapping to the new canonical ID
                cursor.execute("""
                    INSERT OR IGNORE INTO asset_symbol_map (canonical_id, symbol, source, priority, is_active)
                    VALUES (?, ?, 'legacy', 100, 1)
                """, (new_id, old_id))
                
                standardized_count += 1
                
            except Exception as e:
                print(f"  [ERROR] Failed to standardize {old_id}: {e}")
                error_count += 1
        
        conn.commit()
        print(f"\n✅ Migration complete. Standardized: {standardized_count}, Errors: {error_count}")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    standardize_existing_ids()
