from db.connection import get_connection

def migrate():
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Check if column exists
        cursor.execute("PRAGMA table_info(risk_overlay_snapshot)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if "sector_position_pct" in columns:
            print("Column 'sector_position_pct' already exists. Skipping.")
        else:
            print("Adding column 'sector_position_pct'...")
            cursor.execute("ALTER TABLE risk_overlay_snapshot ADD COLUMN sector_position_pct REAL")
            conn.commit()
            print("Migration successful.")
            
    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
