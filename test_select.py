import sqlite3
from db.connection import get_connection

conn = get_connection()
cursor = conn.cursor()
symbol = "US:STOCK:TSLA"
cursor.execute("SELECT close, pe, pb, eps, ps, dividend_yield FROM vera_price_cache WHERE symbol = ? ORDER BY trade_date DESC LIMIT 1", (symbol,))
row = cursor.fetchone()
print(f"Row: {row}")
print(f"close: {row[0]}")
print(f"pe: {row[1]}")
print(f"pb: {row[2]}")
print(f"eps: {row[3]}")
print(f"ps: {row[4]}")
