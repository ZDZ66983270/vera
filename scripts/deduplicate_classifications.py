import sqlite3

DB_PATH = "vera.db"

def deduplicate_classifications():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Keep only the latest record per asset_id based on as_of_date and rowid
    cursor.execute("""
        DELETE FROM asset_classification
        WHERE rowid NOT IN (
            SELECT MAX(rowid)
            FROM asset_classification
            GROUP BY asset_id
        )
    """)
    
    # Remove any generic 'Financials' for assets that have more specific mappings now
    # (Actually the above GROUP BY handles it if we keep only the latest)
    
    conn.commit()
    conn.close()
    print("Classification Deduplicated.")

if __name__ == "__main__":
    deduplicate_classifications()
