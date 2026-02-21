import sqlite3
from data.fetch_fundamentals import fetch_fundamentals
from datetime import datetime

symbol = "US:STOCK:TSLA"
funds, bank = fetch_fundamentals(symbol)
print(f"Symbol: {symbol}")
print(f"Price: {funds.pe_ttm * funds.eps_ttm if funds.pe_ttm and funds.eps_ttm else 'N/A'}")
print(f"EPS: {funds.eps_ttm}")
print(f"PE: {funds.pe_ttm}")
print(f"PB: {funds.pb_ratio}")
print(f"Industry: {funds.industry}")
