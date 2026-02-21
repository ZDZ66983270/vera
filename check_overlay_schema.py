from db.connection import get_connection

def check_schema():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(risk_overlay_snapshot)")
        columns = cursor.fetchall()
        print("Columns in risk_overlay_snapshot:")
        found = False
        for col in columns:
            print(f"- {col[1]} ({col[2]})")
            if col[1] == 'sector_position_pct':
                found = True
        
        if found:
            print("\n✅ sector_position_pct column EXISTS.")
        else:
            print("\n❌ sector_position_pct column MISSING.")
            
    finally:
        conn.close()

if __name__ == "__main__":
    check_schema()
