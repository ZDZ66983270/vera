import sqlite3

def verify_schema():
    conn = sqlite3.connect('vera.db')
    cursor = conn.cursor()
    
    # Get current schema
    cursor.execute("PRAGMA table_info(analysis_snapshot)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}
    
    # Expected columns from INSERT statement
    expected = {
        'snapshot_id': 'TEXT',
        'asset_id': 'TEXT',
        'as_of_date': 'TEXT',
        'risk_level': 'TEXT',
        'valuation_anchor': 'TEXT',
        'valuation_status': 'TEXT',
        'payout_score': 'REAL',
        'is_value_trap': 'INTEGER',
        'created_at': 'TIMESTAMP'
    }
    
    print("Schema Verification:")
    print("=" * 50)
    
    all_good = True
    for col, dtype in expected.items():
        if col in columns:
            print(f"✓ {col:20s} {dtype:15s} - Present")
        else:
            print(f"✗ {col:20s} {dtype:15s} - MISSING")
            all_good = False
    
    print("=" * 50)
    if all_good:
        print("✅ All required columns are present!")
    else:
        print("❌ Some columns are missing!")
    
    conn.close()
    return all_good

if __name__ == "__main__":
    verify_schema()
