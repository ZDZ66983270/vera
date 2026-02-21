import csv
import os
import sys
import sqlite3

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db.connection import get_connection

def import_asset_classification(conn, file_path):
    print(f"\n[INFO] Importing {file_path}...")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(filter(lambda row: not row.strip().startswith('#'), f))
            count = 0
            for row in reader:
                # Basic validation
                if not row.get('asset_id') or not row.get('scheme'):
                    continue
                    
                conn.execute("""
                    INSERT OR REPLACE INTO asset_classification 
                    (asset_id, scheme, sector_code, sector_name, industry_code, industry_name, as_of_date, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    row['asset_id'].strip(),
                    row['scheme'].strip(),
                    row.get('sector_code', '').strip(),
                    row.get('sector_name', '').strip(),
                    row.get('industry_code', '').strip(),
                    row.get('industry_name', '').strip(),
                    row.get('as_of_date', '2025-01-01').strip(),
                    row.get('is_active', '1').strip()
                ))
                count += 1
            print(f"  -> Imported/Updated {count} classification records.")
    except Exception as e:
        print(f"  [ERROR] Failed to import classification: {e}")

def import_sector_proxy_map(conn, file_path):
    print(f"\n[INFO] Importing {file_path}...")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(filter(lambda row: not row.strip().startswith('#'), f))
            count = 0
            for row in reader:
                if not row.get('scheme') or not row.get('sector_code') or not row.get('proxy_etf_id'):
                    continue
                    
                conn.execute("""
                    INSERT OR REPLACE INTO sector_proxy_map 
                    (scheme, sector_code, sector_name, proxy_etf_id, priority, is_active, note)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    row['scheme'].strip(),
                    row['sector_code'].strip(),
                    row.get('sector_name', '').strip(),
                    row['proxy_etf_id'].strip(),
                    row.get('priority', '10').strip(),
                    row.get('is_active', '1').strip(),
                    row.get('note', '').strip()
                ))
                count += 1
            print(f"  -> Imported/Updated {count} sector proxy records.")
    except Exception as e:
        print(f"  [ERROR] Failed to import sector map: {e}")

def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    imports_dir = os.path.join(base_dir, "imports")
    
    conn = get_connection()
    try:
        import_asset_classification(conn, os.path.join(imports_dir, "asset_classification.csv"))
        import_sector_proxy_map(conn, os.path.join(imports_dir, "sector_proxy_map.csv"))
        conn.commit()
        print("\n[SUCCESS] System configuration reloaded from CSVs.")
    except Exception as e:
        print(f"\n[FATAL] Error reloading config: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
