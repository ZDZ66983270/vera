#!/usr/bin/env python3
"""
Fix anomalous price records for Tencent (HK:STOCK:00700)
where high < low values are swapped.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "vera.db"

def fix_anomalous_records():
    """Fix the 2 records with inverted high/low values."""
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("🔍 Checking for anomalous records...")
    
    # Check current values
    cursor.execute("""
        SELECT trade_date, open, high, low, close, volume
        FROM vera_price_cache
        WHERE symbol = 'HK:STOCK:00700' 
        AND trade_date IN ('2009-12-31', '2010-01-15')
        ORDER BY trade_date
    """)
    
    records = cursor.fetchall()
    print(f"\n📊 Found {len(records)} records to fix:\n")
    
    for record in records:
        date, open_p, high, low, close, volume = record
        print(f"  {date}: Open={open_p}, High={high}, Low={low}, Close={close}")
        if high < low:
            print(f"    ⚠️  ANOMALY: High ({high}) < Low ({low})")
    
    # Fix 2009-12-31: swap high and low
    print("\n🔧 Fixing 2009-12-31...")
    cursor.execute("""
        UPDATE vera_price_cache
        SET high = 29.16, low = 28.694
        WHERE symbol = 'HK:STOCK:00700' AND trade_date = '2009-12-31'
    """)
    
    # Fix 2010-01-15: swap high and low
    print("🔧 Fixing 2010-01-15...")
    cursor.execute("""
        UPDATE vera_price_cache
        SET high = 30.353, low = 29.904
        WHERE symbol = 'HK:STOCK:00700' AND trade_date = '2010-01-15'
    """)
    
    conn.commit()
    
    # Verify fixes
    print("\n✅ Verifying fixes...")
    cursor.execute("""
        SELECT trade_date, open, high, low, close, volume
        FROM vera_price_cache
        WHERE symbol = 'HK:STOCK:00700' 
        AND trade_date IN ('2009-12-31', '2010-01-15')
        ORDER BY trade_date
    """)
    
    records = cursor.fetchall()
    print(f"\n📊 Updated records:\n")
    
    all_valid = True
    for record in records:
        date, open_p, high, low, close, volume = record
        print(f"  {date}: Open={open_p}, High={high}, Low={low}, Close={close}")
        if high < low:
            print(f"    ❌ STILL INVALID: High ({high}) < Low ({low})")
            all_valid = False
        else:
            print(f"    ✅ Valid: High >= Low")
    
    # Check for any remaining anomalies
    print("\n🔍 Checking for other anomalies in entire dataset...")
    cursor.execute("""
        SELECT COUNT(*) 
        FROM vera_price_cache
        WHERE symbol = 'HK:STOCK:00700' AND high < low
    """)
    
    anomaly_count = cursor.fetchone()[0]
    
    if anomaly_count == 0:
        print("✅ No anomalies found! All records are valid.")
    else:
        print(f"⚠️  Found {anomaly_count} remaining anomalies")
    
    conn.close()
    
    return all_valid and anomaly_count == 0

if __name__ == "__main__":
    print("=" * 60)
    print("Tencent Price Data Anomaly Fix")
    print("=" * 60)
    
    success = fix_anomalous_records()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ All anomalies fixed successfully!")
    else:
        print("❌ Some issues remain. Please review manually.")
    print("=" * 60)
