import sqlite3
import pandas as pd

conn = sqlite3.connect('vera.db')
cursor = conn.cursor()

# Check the most recently updated records
query = """
SELECT asset_id, report_date, revenue_ttm, net_income_ttm, 
       operating_cashflow, cash_and_equivalents, total_debt, total_loans,
       created_at, updated_at
FROM financial_history 
ORDER BY updated_at DESC 
LIMIT 5
"""

df = pd.read_sql_query(query, conn)
print(df.to_string())
conn.close()
