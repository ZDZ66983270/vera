import csv
import sqlite3

DB_PATH = "vera.db"
CSV_PATH = "imports/sector_proxy_map.csv"

def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create table if not exists
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sector_proxy_map (
      scheme           TEXT NOT NULL,
      sector_code      TEXT NOT NULL,
      sector_name      TEXT,
      proxy_etf_id     TEXT NOT NULL,
      market_index_id  TEXT,
      priority         INTEGER DEFAULT 50,
      is_active        INTEGER DEFAULT 1,
      note             TEXT,
      PRIMARY KEY(scheme, sector_code, proxy_etf_id)
    )
    """)
    
    count = 0
    with open(CSV_PATH, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        if reader.fieldnames:
            reader.fieldnames = [x.strip() for x in reader.fieldnames]
            
        for row in reader:
            if not row or not row.get('scheme'): continue
            if row.get('scheme').startswith('#'): continue  # Skip comments
            if row.get('is_active') == '0': continue
            
            scheme = row.get('scheme', '').strip().upper()
            sector_code = row.get('sector_code', '').strip()
            sector_name = row.get('sector_name', '').strip()
            proxy_etf_id = row.get('proxy_etf_id', '').strip().upper()
            market_index_id = row.get('market_index_id', '').strip().upper()
            priority = int(row.get('priority', 50))
            is_active = int(row.get('is_active', 1))
            note = row.get('note', '').strip()
            
            if not scheme or not sector_code or not proxy_etf_id:
                continue
            
            print(f"Importing {scheme}:{sector_code} -> ETF:{proxy_etf_id}, Index:{market_index_id}")
            
            sql = """INSERT OR REPLACE INTO sector_proxy_map
                (scheme, sector_code, sector_name, proxy_etf_id, market_index_id, priority, is_active, note)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)"""
            cursor.execute(sql, (scheme, sector_code, sector_name, proxy_etf_id, market_index_id, priority, is_active, note))
            count += 1
            
    conn.commit()
    conn.close()
    print(f"\n✅ Successfully imported {count} sector proxy mappings.")

if __name__ == "__main__":
    main()
