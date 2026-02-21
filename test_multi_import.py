import pandas as pd
import io
import sqlite3
from utils.csv_handler import parse_and_import_csv
from db.connection import get_connection

def test_multi_symbol_import():
    # 模拟包含多个标的的 CSV
    csv_content = """Date,Symbol,Close
2023-01-01,SYM_A,100
2023-01-01,SYM_B,200
2023-01-02,SYM_A,105
2023-01-02,SYM_B,195
"""
    file_obj = io.BytesIO(csv_content.encode('utf-8'))
    
    print("Testing multi-symbol import...")
    success, msg = parse_and_import_csv(file_obj)
    print(f"Result: {success}, Message: {msg}")
    
    if success:
        conn = get_connection()
        # 验证 SYM_A
        count_a = conn.execute("SELECT COUNT(*) FROM vera_price_cache WHERE symbol='SYM_A'").fetchone()[0]
        # 验证 SYM_B
        count_b = conn.execute("SELECT COUNT(*) FROM vera_price_cache WHERE symbol='SYM_B'").fetchone()[0]
        conn.close()
        print(f"Verification: SYM_A has {count_a} records, SYM_B has {count_b} records.")

if __name__ == "__main__":
    test_multi_symbol_import()
