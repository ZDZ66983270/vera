import sqlite3
import pandas as pd
import os

db_path = "/Users/zhangzy/My Docs/Privates/22-AI编程/VERA/vera.db"
conn = sqlite3.connect(db_path)

print("Markets and Asset Types in assets table:")
df_assets = pd.read_sql_query("SELECT DISTINCT market, asset_type FROM assets", conn)
print(df_assets)

print("\nMarkets and Asset Types in universe (active):")
query = """
    SELECT DISTINCT a.market, a.asset_type 
    FROM asset_universe u 
    JOIN assets a ON u.asset_id = a.asset_id 
    WHERE u.is_active = 1
"""
df_universe = pd.read_sql_query(query, conn)
print(df_universe)

conn.close()
