import pandas as pd
import sqlite3
from utils.csv_handler import parse_and_import_financials_csv

csv_path = "imports/financial_history.csv"
success, message = parse_and_import_financials_csv(csv_path)
print(f"Success: {success}")
print(f"Message: {message}")
