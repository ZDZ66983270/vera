from db.connection import init_db
from data.fetch_fundamentals import fetch_fundamentals
from datetime import datetime

init_db()
print("--- TSLA ---")
f, _ = fetch_fundamentals("TSLA")
print(f"dividend_yield: {f.dividend_yield}")
print(f"buyback_ratio: {f.buyback_ratio}")
print(f"no_dividend_history: {f.no_dividend_history}")
print(f"listing_years: {f.listing_years}")

print("\n--- MSFT ---")
f, _ = fetch_fundamentals("MSFT")
print(f"dividend_yield: {f.dividend_yield}")
print(f"buyback_ratio: {f.buyback_ratio}")
print(f"no_dividend_history: {f.no_dividend_history}")
print(f"listing_years: {f.listing_years}")
