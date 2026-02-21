
from utils.stock_name_fetcher import get_stock_name
print(f"Name for HK:STOCK:00005: {get_stock_name('HK:STOCK:00005')}")

from db.connection import get_connection
conn = get_connection()
row = conn.execute("SELECT name FROM assets WHERE asset_id='HK:STOCK:00005'").fetchone()
print(f"Current DB Name: {row[0] if row else 'Not Found'}")
conn.close()
