import sqlite3
import os
from db.connection import get_connection

def migrate_benchmarks():
    print("--- Starting Benchmark Migration to asset_universe ---")
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # 1. Fetch all assets in the universe
        cursor.execute("SELECT asset_id FROM asset_universe WHERE is_active = 1")
        universe_assets = [row['asset_id'] for row in cursor.fetchall()]
        
        for asset_id in universe_assets:
            print(f"Processing benchmarks for: {asset_id}")
            
            # Fetch market
            cursor.execute("SELECT market FROM assets WHERE asset_id = ?", (asset_id,))
            m_row = cursor.fetchone()
            market = m_row['market'] if m_row else 'US'
            
            # 2. Find classification
            query = """
                SELECT scheme, sector_code 
                FROM asset_classification 
                WHERE asset_id = ? AND is_active = 1 
                ORDER BY as_of_date DESC, scheme DESC LIMIT 1
            """
            cursor.execute(query, (asset_id,))
            class_row = cursor.fetchone()
            
            if class_row:
                scheme = class_row['scheme']
                sector_code = class_row['sector_code']
                
                # 3. Find default benchmarks from mapping
                map_query = """
                    SELECT proxy_etf_id, market_index_id 
                    FROM sector_proxy_map 
                    WHERE scheme = ? AND sector_code = ? AND market = ? AND is_active = 1
                    LIMIT 1
                """
                cursor.execute(map_query, (scheme, sector_code, market))
                map_row = cursor.fetchone()
                
                if map_row:
                    proxy_etf = map_row['proxy_etf_id']
                    market_index = map_row['market_index_id']
                    
                    # 4. Update asset_universe
                    cursor.execute("""
                        UPDATE asset_universe 
                        SET sector_proxy_id = ?, market_index_id = ? 
                        WHERE asset_id = ?
                    """, (proxy_etf, market_index, asset_id))
                    print(f"  [OK] Set ETF={proxy_etf}, Index={market_index}")
                else:
                    print(f"  [WARN] No mapping found for {scheme}:{sector_code} in {market}")
            else:
                print(f"  [WARN] No classification record found for {asset_id}")
        
        conn.commit()
        print("\n✅ Migration complete.")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_benchmarks()
