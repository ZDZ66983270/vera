import sqlite3
import os

DB_PATH = "vera.db"

def clean_assets():
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    targets = [
        "HK:STOCK:01211",
        "CN:STOCK:000001",
        "CN:STOCK:000300"
    ]

    print(f"🧹 Cleaning Ghost Assets from: {DB_PATH}")
    print("-" * 50)

    deleted_count = 0
    for target_id in targets:
        # Check if exists first for logging
        cursor.execute("SELECT symbol_name, asset_type FROM assets WHERE asset_id = ?", (target_id,))
        record = cursor.fetchone()
        
        if record:
            try:
                # Execute deletion
                cursor.execute("DELETE FROM assets WHERE asset_id = ?", (target_id,))
                if cursor.rowcount > 0:
                    print(f"✅ DELETED: {target_id} ({record[0]}, Type: {record[1]})")
                    deleted_count += 1
                else:
                    print(f"⚠️  Failed to delete {target_id}")
            except Exception as e:
                print(f"❌ Error deleting {target_id}: {e}")
        else:
            print(f"ℹ️  Record not found (already gone): {target_id}")

    conn.commit()
    print("-" * 50)
    print(f"Total records deleted: {deleted_count}")
    
    # Verify remaining specific indices to ensure we didn't touch the 'INDEX' versions
    verify_list = ["CN:INDEX:000001", "CN:INDEX:000300"]
    print("\n🔍 Verifying CORRECT records still exist:")
    for v_id in verify_list:
        cursor.execute("SELECT asset_id, asset_type FROM assets WHERE asset_id = ?", (v_id,))
        row = cursor.fetchone()
        if row:
             print(f"✅ PRESERVED: {row[0]} (Type: {row[1]})")
        else:
             print(f"❌ WARNING: {v_id} is missing!")

    conn.close()

if __name__ == "__main__":
    clean_assets()
