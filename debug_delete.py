import sqlite3
import pandas as pd
import sys

def get_connection():
    return sqlite3.connect('vera.db')

def delete_snapshot(snapshot_id: str):
    """Exact copy of the function in app.py"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        
        # 手动清理没有级联删除的关联表
        cursor.execute("DELETE FROM risk_overlay_snapshot WHERE snapshot_id = ?", (snapshot_id,))
        cursor.execute("DELETE FROM sector_risk_snapshot WHERE snapshot_id = ?", (snapshot_id,))
        cursor.execute("DELETE FROM quality_snapshot WHERE snapshot_id = ?", (snapshot_id,))
        
        # 清理主表
        cursor.execute("DELETE FROM analysis_snapshot WHERE snapshot_id = ?", (snapshot_id,))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False

def test():
    conn = get_connection()
    df = pd.read_sql("SELECT snapshot_id, asset_id, created_at FROM analysis_snapshot LIMIT 5", conn)
    conn.close()
    
    if df.empty:
        print("No snapshots found.")
        return

    print("Available snapshots:")
    print(df)
    
    target_id = df.iloc[0]['snapshot_id']
    print(f"\nDeleting snapshot: {target_id}")
    
    if delete_snapshot(target_id):
        print("Success!")
        conn = get_connection()
        check = pd.read_sql("SELECT count(*) as count FROM analysis_snapshot WHERE snapshot_id = ?", conn, params=(target_id,))
        print(f"Remaining count: {check['count'][0]}")
        conn.close()
    else:
        print("Failed.")

if __name__ == "__main__":
    test()
