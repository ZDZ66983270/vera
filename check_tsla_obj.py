import sqlite3
from data.fetch_fundamentals import fetch_fundamentals
from datetime import datetime

symbol = "US:STOCK:TSLA"
fund, bank = fetch_fundamentals(symbol)
print(f"Symbol: {fund.symbol}")
print(f"Industry: {fund.industry}")
print(f"EPS TTM: {fund.eps_ttm}")
print(f"PE TTM: {fund.pe_ttm}")
print(f"Net Profit TTM: {fund.net_profit_ttm}")
print(f"PB Ratio: {fund.pb_ratio}")
