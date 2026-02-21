#!/usr/bin/env python3
"""
Diagnostic script to check evaluation history for AAPL
"""
import sqlite3
import pandas as pd

# Connect to database
conn = sqlite3.connect('stock_analysis.db')

print("=== Checking analysis_snapshot table ===\n")

# Check total records
total = pd.read_sql_query("SELECT COUNT(*) as count FROM analysis_snapshot", conn)
print(f"Total snapshots in database: {total['count'].iloc[0]}\n")

# Check distinct asset_ids
print("Sample of asset_ids in analysis_snapshot:")
asset_ids = pd.read_sql_query("""
    SELECT DISTINCT asset_id 
    FROM analysis_snapshot 
    ORDER BY created_at DESC 
    LIMIT 20
""", conn)
print(asset_ids)
print()

# Check for AAPL variations
print("Checking for AAPL variations:")
aapl_variations = pd.read_sql_query("""
    SELECT DISTINCT asset_id 
    FROM analysis_snapshot 
    WHERE asset_id LIKE '%AAPL%'
""", conn)
print(f"Found {len(aapl_variations)} variations:")
print(aapl_variations)
print()

# Check assets table
print("=== Checking assets table ===\n")
aapl_assets = pd.read_sql_query("""
    SELECT asset_id, symbol, name, market 
    FROM assets 
    WHERE symbol LIKE '%AAPL%' OR asset_id LIKE '%AAPL%'
""", conn)
print("AAPL entries in assets table:")
print(aapl_assets)
print()

# Check if there are any snapshots for US stocks
us_snapshots = pd.read_sql_query("""
    SELECT asset_id, COUNT(*) as count
    FROM analysis_snapshot
    WHERE asset_id LIKE 'US:%'
    GROUP BY asset_id
    ORDER BY count DESC
    LIMIT 10
""", conn)
print("Sample US stock snapshots:")
print(us_snapshots)

conn.close()
