#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect('/Users/zhangzy/My Docs/Privates/22-AI编程/VERA/stock_analysis.db')
cursor = conn.cursor()

print("=== Checking analysis_snapshot table ===")
try:
    total = cursor.execute("SELECT COUNT(*) FROM analysis_snapshot").fetchone()[0]
    print(f"Total snapshots: {total}")
    
    if total > 0:
        print("\nSample asset_ids:")
        samples = cursor.execute("SELECT DISTINCT asset_id FROM analysis_snapshot LIMIT 10").fetchall()
        for row in samples:
            print(f"  - {row[0]}")
except Exception as e:
    print(f"Error: {e}")

conn.close()
