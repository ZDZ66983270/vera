import sqlite3
import pandas as pd
from core.earnings_state import determine_earnings_state

conn = sqlite3.connect('vera.db')
rows = conn.execute("SELECT report_date, eps_ttm FROM financial_history WHERE asset_id='HK:STOCK:03968' ORDER BY report_date ASC").fetchall()
conn.close()

eps_series = []
for r in rows:
    if r[1] is not None:
        eps_series.append((r[0], float(r[1])))

print("EPS Series length:", len(eps_series))
if len(eps_series) > 0:
    print("Latest 5 EPS:", eps_series[-5:])
    
state = determine_earnings_state(eps_series)
print("Earnings State:", state)
