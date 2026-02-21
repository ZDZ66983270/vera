from datetime import datetime
from data.fetch_fundamentals import fetch_fundamentals

symbol = "HK:STOCK:00700"
as_of_date = datetime(2025, 1, 22)

print(f"Fetching fundamentals for {symbol} on {as_of_date}...")
fund, bank = fetch_fundamentals(symbol, as_of_date)

print(f"PE TTM: {fund.pe_ttm}")
print(f"Net Profit: {fund.net_profit_ttm}")
print(f"Valuation Status: {fund.current_valuation_status}")
print(f"Revenue: {fund.revenue_ttm}")
