
import sqlite3
import os
import sys

sys.path.append(os.getcwd())
try:
    from db.connection import get_connection
except ImportError:
    # Fallback if module path issues
    def get_connection():
        return sqlite3.connect("vera.db")

def backfill():
    conn = get_connection()
    cursor = conn.cursor()
    
    print("Backfilling market and asset_type in assets table...")
    try:
        cursor.execute("SELECT asset_id FROM assets")
        rows = cursor.fetchall()
        
        count = 0
        for (aid,) in rows:
            parts = aid.split(':')
            if len(parts) >= 3:
                market = parts[0]
                atype = parts[1]
                
                cursor.execute("UPDATE assets SET market = ?, asset_type = ? WHERE asset_id = ?", 
                               (market, atype, aid))
                count += 1
                
        conn.commit()
        print(f"Successfully updated {count} assets.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    backfill()
