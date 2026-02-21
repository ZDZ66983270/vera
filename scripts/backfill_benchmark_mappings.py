#!/usr/bin/env python3
"""
Backfill missing benchmark symbol mappings for existing assets.
"""

import sqlite3
from db.connection import get_connection
from utils.canonical_resolver import resolve_symbol_for_provider

def backfill_benchmark_mappings():
    print("--- Backfilling Benchmark Symbol Mappings ---")
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Find all unique benchmarks referenced in asset_universe
        cursor.execute("""
            SELECT DISTINCT sector_proxy_id FROM asset_universe 
            WHERE sector_proxy_id IS NOT NULL AND sector_proxy_id != '' AND is_active = 1
            UNION
            SELECT DISTINCT market_index_id FROM asset_universe 
            WHERE market_index_id IS NOT NULL AND market_index_id != '' AND is_active = 1
        """)
        benchmarks = [r[0] for r in cursor.fetchall()]
        
        added_count = 0
        
        for benchmark_id in benchmarks:
            # Check if mapping exists
            existing = cursor.execute(
                "SELECT 1 FROM asset_symbol_map WHERE canonical_id = ? AND is_active = 1 LIMIT 1",
                (benchmark_id,)
            ).fetchone()
            
            if existing:
                continue
            
            # Create mapping using resolve_symbol_for_provider
            try:
                provider_symbol = resolve_symbol_for_provider(benchmark_id, "yahoo")
                cursor.execute("""
                    INSERT OR IGNORE INTO asset_symbol_map (canonical_id, symbol, source, priority, is_active)
                    VALUES (?, ?, 'yahoo', 50, 1)
                """, (benchmark_id, provider_symbol))
                print(f"  [ADD] {benchmark_id} -> {provider_symbol}")
                added_count += 1
            except Exception as e:
                print(f"  [SKIP] {benchmark_id}: {e}")
        
        conn.commit()
        print(f"\n✅ Backfill complete. Added {added_count} benchmark mappings.")
        
    except Exception as e:
        print(f"❌ Backfill failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    backfill_benchmark_mappings()
