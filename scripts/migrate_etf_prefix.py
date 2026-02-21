import sqlite3

DB_PATH = "vera.db"

def migrate_etf_prefixes():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Correct Table and Column Map
    # Map: (table_name, column_name)
    tables_to_update = [
        ("assets", "asset_id"),
        ("asset_classification", "asset_id"),
        ("sector_proxy_map", "proxy_etf_id"),
        ("asset_symbol_map", "canonical_id"),
        ("vera_price_cache", "symbol"), # It's 'symbol' in price_cache
        ("analysis_snapshot", "asset_id"),
        ("quality_snapshot", "asset_id"),
        ("risk_card_snapshot", "asset_id"),
        ("risk_events", "asset_id"),
        ("drawdown_state_history", "asset_id")
    ]
    
    print("--- [1] Correcting asset_type in assets table ---")
    cursor.execute("""
        UPDATE assets 
        SET asset_type = 'ETF' 
        WHERE asset_id LIKE '%:STOCK:%' AND (
            asset_id LIKE '%:51%' OR asset_id LIKE '%:15%' OR asset_id LIKE '%:58%' 
            OR asset_id IN ('HK:STOCK:02800', 'HK:STOCK:03033', 'HK:STOCK:02822', 'HK:STOCK:02828', 'HK:STOCK:03067')
        )
    """)
    
    print("--- [2] Migrating ID prefixes ---")
    for table, col in tables_to_update:
        try:
            print(f"Migrating {table}.{col}...")
            # Pattern-based migration for ETFs
            cursor.execute(f"""
                UPDATE {table}
                SET {col} = REPLACE({col}, ':STOCK:', ':ETF:')
                WHERE {col} LIKE '%:STOCK:%' AND (
                    {col} LIKE '%:51%' OR {col} LIKE '%:15%' OR {col} LIKE '%:58%'
                    OR {col} IN ('HK:STOCK:02800', 'HK:STOCK:03033', 'HK:STOCK:02822', 'HK:STOCK:02828', 'HK:STOCK:03067')
                    OR EXISTS (
                        SELECT 1 FROM assets a 
                        WHERE a.asset_id = {table}.{col} AND a.asset_type = 'ETF'
                    )
                )
            """)
        except Exception as e:
            print(f"Warning: Could not update {table}.{col}: {e}")

    # 3. Special case for vera_snapshot (ID might be handled differently or missing)
    try:
        cursor.execute("UPDATE vera_snapshot SET asset_id = REPLACE(asset_id, ':STOCK:', ':ETF:') WHERE asset_id LIKE '%:STOCK:%'")
    except:
        pass

    # 4. Final Verification
    cursor.execute("SELECT asset_id, asset_type FROM assets WHERE asset_id LIKE '%:ETF:%' LIMIT 5")
    rows = cursor.fetchall()
    print("Sample Migrated IDs:")
    for r in rows:
        print(f"  {r[0]} ({r[1]})")

    conn.commit()
    conn.close()
    print("Migration Success.")

if __name__ == "__main__":
    migrate_etf_prefixes()
