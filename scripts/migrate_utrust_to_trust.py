import sqlite3
from db.connection import get_connection

def migrate_utrust_to_trust():
    conn = get_connection()
    cursor = conn.cursor()
    
    print("Starting migration: UTRUST -> TRUST")
    
    try:
        # 1. Identify assets to migrate
        rows = cursor.execute("SELECT asset_id FROM assets WHERE asset_id LIKE '%:UTRUST:%'").fetchall()
        assets_to_migrate = [r[0] for r in rows]
        print(f"Found {len(assets_to_migrate)} assets to migrate: {assets_to_migrate}")
        
        for old_id in assets_to_migrate:
            new_id = old_id.replace(":UTRUST:", ":TRUST:")
            print(f"Migrating {old_id} -> {new_id}")
            
            # A. Update asset_universe
            # Check if new_id already exists (unlikely but possible)
            exists = cursor.execute("SELECT 1 FROM asset_universe WHERE asset_id = ?", (new_id,)).fetchone()
            if not exists:
                cursor.execute("UPDATE asset_universe SET asset_id = ? WHERE asset_id = ?", (new_id, old_id))
            else:
                print(f"Warning: {new_id} already exists in universe. Deleting old entry.")
                cursor.execute("DELETE FROM asset_universe WHERE asset_id = ?", (old_id,))
                
            # B. Update asset_classification
            cursor.execute("UPDATE asset_classification SET asset_id = ? WHERE asset_id = ?", (new_id, old_id))
            
            # C. Update asset_symbol_map canonical_id
            cursor.execute("UPDATE asset_symbol_map SET canonical_id = ? WHERE canonical_id = ?", (new_id, old_id))
            
            # D. Update assets table
            # assets table has asset_id as PK.
            # We must INSERT new, DELETE old (or UPDATE id if supported and no conflict)
            # SQLite supports UPDATE of PK if no conflict.
            try:
                cursor.execute("UPDATE assets SET asset_id = ?, asset_type = 'TRUST' WHERE asset_id = ?", (new_id, old_id))
            except sqlite3.IntegrityError:
                # Conflict? duplicate?
                print(f"Conflict updating assets table for {new_id}. Checking properties.")
                # If new ID exists, we just update type and delete old?
                cursor.execute("UPDATE assets SET asset_type = 'TRUST' WHERE asset_id = ?", (new_id,))
                cursor.execute("DELETE FROM assets WHERE asset_id = ?", (old_id,))

        # 2. Update 'assets' table records where asset_type = 'UTRUST' but ID wasn't caught?
        # (Should be caught by loop above if ID consistent)
        cursor.execute("UPDATE assets SET asset_type = 'TRUST' WHERE asset_type = 'UTRUST'")
        
        # 3. Update vera_price_cache ?
        # Symbols there are 'US:TRUST:...' already as per check.
        # But verify.
        rows_pc = cursor.execute("SELECT DISTINCT symbol FROM vera_price_cache WHERE symbol LIKE '%:UTRUST:%'").fetchall()
        if rows_pc:
            print(f"Found {len(rows_pc)} price cache symbols to migrate.")
            cursor.execute("UPDATE vera_price_cache SET symbol = REPLACE(symbol, ':UTRUST:', ':TRUST:') WHERE symbol LIKE '%:UTRUST:%'")
        
        conn.commit()
        print("Migration complete successfully.")
        
    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_utrust_to_trust()
