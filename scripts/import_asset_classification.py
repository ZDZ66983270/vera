import csv
import sqlite3
import re
import os

DB_PATH = "vera.db"
CSV_PATH = "imports/asset_classification.csv"

def get_connection():
    return sqlite3.connect(DB_PATH)

def resolve_asset_id(symbol):
    symbol = symbol.strip().upper()
    # CN Logic
    if re.match(r'^\d{6}\.(SH|SZ|SS)$', symbol):
        return f"CN:STOCK:{symbol[:6]}"
    if re.match(r'^\d{6}$', symbol):
        return f"CN:STOCK:{symbol}"
    # US Logic
    if ' ' in symbol:
        symbol = symbol.split(' ')[0]
    # Check if suffix HK
    if symbol.endswith(".HK"):
        return f"HK:STOCK:{symbol[:5]}"
    return symbol

def main():
    if not os.path.exists(CSV_PATH):
        print(f"Error: {CSV_PATH} not found.")
        return

    conn = get_connection()
    cursor = conn.cursor()
    
    count = 0
    with open(CSV_PATH, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        if reader.fieldnames:
            reader.fieldnames = [x.strip() for x in reader.fieldnames]
            
        for row in reader:
            if not row or not row.get('asset_id'): continue
            if row.get('is_active') == '0': continue
            
            raw_id = row['asset_id']
            asset_id = resolve_asset_id(raw_id)
            
            sector = row.get('sector_name')
            industry = row.get('industry_name')
            
            print(f"Updating {asset_id} -> Sector: {sector}, Industry: {industry}")
            
            # Upsert into asset_classification table
            sql_ac = """INSERT OR REPLACE INTO asset_classification
                (asset_id, scheme, sector_code, sector_name, industry_code, industry_name, as_of_date, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)"""
            cursor.execute(sql_ac, (
                asset_id,
                row.get('scheme'),
                row.get('sector_code'),
                sector,
                row.get('industry_code'),
                industry,
                row.get('as_of_date'),
                int(row.get('is_active') or 1)
            ))

            # Update assets table (keep existing behavior)
            sql = "UPDATE assets SET industry = ? WHERE asset_id = ?"
            cursor.execute(sql, (sector, asset_id))
            count += 1
            
    conn.commit()
    conn.close()
    print(f"Successfully updated classification for {count} assets.")

if __name__ == "__main__":
    main()
