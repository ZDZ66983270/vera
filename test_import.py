import pandas as pd
import io
import os
from utils.csv_handler import parse_and_import_csv
from db.connection import get_connection

def test_csv_import():
    # 模拟 CSV 数据
    csv_content = """Date,Close,Volume
2023-01-01,100,1000
2023-01-02,105,1100
2023-01-03,95,900
2023-01-04,110,1200
"""
    file_obj = io.BytesIO(csv_content.encode('utf-8'))
    
    asset_id = "TEST_CSV_01"
    asset_name = "测试CSV个股"
    
    print(f"Testing import for {asset_id}...")
    success, msg = parse_and_import_csv(file_obj, asset_id, asset_name)
    print(f"Result: {success}, Message: {msg}")
    
    if success:
        # 验证数据库中是否有记录
        conn = get_connection()
        count = conn.execute("SELECT COUNT(*) FROM vera_price_cache WHERE symbol=?", (asset_id,)).fetchone()[0]
        name = conn.execute("SELECT symbol_name FROM assets WHERE asset_id=?", (asset_id,)).fetchone()[0]
        conn.close()
        print(f"Verification: Found {count} price records, Asset name in DB: {name}")

if __name__ == "__main__":
    test_csv_import()
