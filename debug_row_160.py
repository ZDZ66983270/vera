
import pandas as pd
import sqlite3
import os
import sys

# Add project root to path
sys.path.append('/Users/zhangzy/My Docs/Privates/22-AI编程/VERA')

from db.connection import get_connection
from utils.csv_handler import parse_and_import_financials_csv

# We want to see the error for row 160 (AMZN 2021-09-30)
def debug_specific_row(csv_path, target_row_idx):
    df = pd.read_csv(csv_path)
    # We only take the specific row to isolate
    row_data = df.iloc[[target_row_idx - 2]] # idx 160 is row 160, so df index 158? Wait, row 2 is index 0.
    # Actually, Row 160 in CSV is index 158.
    
    print(f"Detail for Row {target_row_idx}:")
    print(row_data[['symbol', 'as_of_date']])
    
    # Save to temp csv
    tmp_path = "tmp_debug.csv"
    row_data.to_csv(tmp_path, index=False)
    
    # Run import
    success, msg = parse_and_import_financials_csv(tmp_path, mode="overwrite")
    print(f"Result: Success={success}, Msg={msg}")
    
    os.remove(tmp_path)

if __name__ == "__main__":
    # We saw Row 160 missing in consistency check
    debug_specific_row('/Users/zhangzy/My Docs/Privates/22-AI编程/VERA/imports/all_financials.csv', 160)
