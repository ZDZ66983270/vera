#!/usr/bin/env python3
"""
Migrate existing vera_price_cache data to canonical symbols
Handles duplicates by keeping the latest entry per (canonical_id, trade_date)
"""
import sqlite3
from datetime import datetime

DB_PATH = "vera.db"

def resolve_canonical_symbol(conn, symbol):
    """Resolve symbol to canonical_id via asset_symbol_map"""
    cursor = conn.cursor()
    result = cursor.execute("""
        SELECT canonical_id FROM asset_symbol_map
        WHERE symbol = ? AND is_active = 1
        ORDER BY priority ASC
        LIMIT 1
    """, (symbol,)).fetchone()
    
    return result[0] if result else symbol

def main():
    print("=" * 60)
    print("VERA Price Cache - Canonical Symbol Migration")
    print("=" * 60)
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Step 1: Identify non-canonical symbols
    print("\n[1] Identifying non-canonical symbols...")
    non_canonical = cursor.execute("""
        SELECT DISTINCT p.symbol
        FROM vera_price_cache p
        LEFT JOIN asset_symbol_map m ON p.symbol = m.canonical_id
        WHERE m.canonical_id IS NULL
          AND EXISTS (
              SELECT 1 FROM asset_symbol_map
              WHERE symbol = p.symbol AND is_active = 1
          )
    """).fetchall()
    
    symbols_to_migrate = [row["symbol"] for row in non_canonical]
    print(f"Found {len(symbols_to_migrate)} non-canonical symbols: {symbols_to_migrate}")
    
    if not symbols_to_migrate:
        print("\n✅ No migration needed - all symbols are already canonical!")
        conn.close()
        return
    
    # Step 2: Create temporary migration table
    print("\n[2] Creating temporary migration table...")
    cursor.execute("""
        CREATE TEMP TABLE price_cache_migration AS
        SELECT
            symbol as old_symbol,
            trade_date,
            open, high, low, close, volume, source,
            rowid
        FROM vera_price_cache
        WHERE symbol IN ({})
    """.format(','.join('?' * len(symbols_to_migrate))), symbols_to_migrate)
    
    migration_count = cursor.execute("SELECT COUNT(*) FROM price_cache_migration").fetchone()[0]
    print(f"Staged {migration_count} rows for migration")
    
    # Step 3: Map to canonical and update
    print("\n[3] Mapping to canonical symbols and updating...")
    
    migrated_rows = cursor.execute("SELECT * FROM price_cache_migration").fetchall()
    updates = []
    conflicts = []
    
    for row in migrated_rows:
        old_symbol = row["old_symbol"]
        canonical = resolve_canonical_symbol(conn, old_symbol)
        
        if canonical == old_symbol:
            continue  # Already canonical (shouldn't happen)
        
        # Update source to include raw symbol
        new_source = row["source"]
        if old_symbol not in new_source:
            new_source = f"{new_source}|raw:{old_symbol}"
        
        # Check for conflict (canonical symbol + trade_date already exists)
        existing = cursor.execute("""
            SELECT rowid FROM vera_price_cache
            WHERE symbol = ? AND trade_date = ? AND rowid != ?
        """, (canonical, row["trade_date"], row["rowid"])).fetchone()
        
        if existing:
            conflicts.append({
                "old_symbol": old_symbol,
                "canonical": canonical,
                "trade_date": row["trade_date"],
                "old_rowid": row["rowid"],
                "existing_rowid": existing[0]
            })
            # Delete the duplicate (keep the existing canonical one)
            cursor.execute("DELETE FROM vera_price_cache WHERE rowid = ?", (row["rowid"],))
        else:
            # Update to canonical
            cursor.execute("""
                UPDATE vera_price_cache
                SET symbol = ?, source = ?
                WHERE rowid = ?
            """, (canonical, new_source, row["rowid"]))
            updates.append({"old": old_symbol, "new": canonical, "date": row["trade_date"]})
    
    conn.commit()
    
    # Step 4: Report results
    print(f"\n[4] Migration complete!")
    print(f"  ✓ Updated: {len(updates)} rows")
    print(f"  ✓ Deleted (duplicates): {len(conflicts)} rows")
    
    if updates:
        print("\n  Sample updates:")
        for u in updates[:5]:
            print(f"    {u['old']} → {u['new']} ({u['date']})")
    
    if conflicts:
        print("\n  Sample conflicts resolved:")
        for c in conflicts[:5]:
            print(f"    Deleted {c['old_symbol']} ({c['trade_date']}) - canonical {c['canonical']} already exists")
    
    # Step 5: Verification
    print("\n[5] Verification...")
    remaining_non_canonical = cursor.execute("""
        SELECT COUNT(DISTINCT p.symbol)
        FROM vera_price_cache p
        WHERE p.symbol LIKE '%.SS' OR p.symbol LIKE '%.SH' OR p.symbol LIKE '%.SZ'
    """).fetchone()[0]
    
    if remaining_non_canonical > 0:
        print(f"  ⚠️  Warning: {remaining_non_canonical} symbols still have suffixes (may be unmapped)")
    else:
        print("  ✅ All A-share symbols are now canonical!")
    
    # Show canonical symbol distribution
    canonical_symbols = cursor.execute("""
        SELECT symbol, COUNT(*) as cnt
        FROM vera_price_cache
        WHERE symbol IN (SELECT canonical_id FROM asset_symbol_map WHERE is_active = 1)
        GROUP BY symbol
        ORDER BY cnt DESC
        LIMIT 10
    """).fetchall()
    
    print("\n  Top canonical symbols:")
    for row in canonical_symbols:
        print(f"    {row['symbol']}: {row['cnt']} rows")
    
    conn.close()
    print("\n" + "=" * 60)
    print("Migration complete! ✅")
    print("=" * 60)

if __name__ == "__main__":
    main()
