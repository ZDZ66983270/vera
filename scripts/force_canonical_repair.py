import sqlite3
import os
import sys
from db.connection import get_connection
from utils.canonical_resolver import resolve_canonical_symbol

def smart_migrate():
    conn = get_connection()
    cursor = conn.cursor()
    
    print("🔍 Searching for non-canonical symbols in price cache...")
    cursor.execute("SELECT DISTINCT symbol FROM vera_price_cache WHERE symbol NOT LIKE '%:%'")
    raw_symbols = [r[0] for r in cursor.fetchall()]
    
    if not raw_symbols:
        print("✅ No non-canonical symbols found.")
        return

    print(f"📦 Found {len(raw_symbols)} types of non-canonical symbols.")
    
    for raw in raw_symbols:
        try:
            canonical = resolve_canonical_symbol(conn, raw)
            if canonical != raw:
                print(f"🔄 Migrating: {raw} -> {canonical}")
                
                # Check for existing records in target to avoid UPSERT conflicts here
                # We do it row by row for safety in this repair script
                cursor.execute("SELECT trade_date, close FROM vera_price_cache WHERE symbol = ?", (raw,))
                rows = cursor.fetchall()
                
                for trade_date, close in rows:
                    # Update or Ignore (prefer existing canonical data if exists)
                    cursor.execute("""
                        INSERT INTO vera_price_cache (symbol, trade_date, close, open, high, low, volume, source)
                        SELECT ?, trade_date, close, open, high, low, volume, source || '|migrated_from:' || ?
                        FROM vera_price_cache WHERE symbol = ? AND trade_date = ?
                        ON CONFLICT(symbol, trade_date) DO UPDATE SET
                           close = excluded.close,
                           source = excluded.source
                    """, (canonical, raw, raw, trade_date))
                
                # Delete old after migration
                cursor.execute("DELETE FROM vera_price_cache WHERE symbol = ?", (raw,))
                conn.commit()
                print(f"   Done: {len(rows)} records moved.")
            else:
                print(f"   Skipping: {raw} (no clear resolution)")
        except Exception as e:
            print(f"   ❌ Error processing {raw}: {e}")

    conn.close()
    print("🚀 Migration finished.")

if __name__ == "__main__":
    smart_migrate()
