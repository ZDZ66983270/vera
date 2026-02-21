from db.connection import get_connection

def inspect_snapshot(symbol):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Check column existence again just to be sure
        cursor.execute("PRAGMA table_info(risk_overlay_snapshot)")
        cols = [c[1] for c in cursor.fetchall()]
        print(f"Columns in DB: {cols}")
        if 'sector_position_pct' not in cols:
            print("CRITICAL: sector_position_pct column is STILL MISSING!")
            return

        print(f"\nFetching latest snapshot for {symbol}...")
        cursor.execute("""
            SELECT snapshot_id, created_at, sector_position_pct, sector_etf_id 
            FROM risk_overlay_snapshot 
            WHERE asset_id = ? 
            ORDER BY created_at DESC LIMIT 1
        """, (symbol,))
        row = cursor.fetchone()
        
        if row:
            print(f"Snapshot ID: {row[0]}")
            print(f"Created At: {row[1]}")
            print(f"Sector Position Pct: {row[2]}")
            print(f"Sector ETF ID: {row[3]}")
        else:
            print("No snapshot found for this asset.")
            
    finally:
        conn.close()

if __name__ == "__main__":
    inspect_snapshot("CN:STOCK:600036")
