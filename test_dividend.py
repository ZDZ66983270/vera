import sqlite3
import pandas as pd
import numpy as np
from core.dividend_engine import evaluate_dividend_safety, DividendFacts

conn = sqlite3.connect('vera.db')
rows = conn.execute("SELECT report_date, dividend_amount, net_profit_ttm FROM financial_history WHERE asset_id='HK:STOCK:03968' ORDER BY report_date ASC").fetchall()
conn.close()

div_history = []
for r in rows:
    if r[1] is not None:
        div_history.append(float(r[1]))
        
print("Dividend history length:", len(div_history))
print("Last 10 dividend items:", div_history[-10:])
if len(div_history) > 0:
    current_div = div_history[-1]
    hist_5y = div_history[-5:]
    mean_5y = np.mean(hist_5y) if hist_5y else None
    std_5y = np.std(hist_5y) if len(hist_5y) > 1 else 0.0
    hist_10y = div_history[-10:]
    cut_count = 0
    if len(hist_10y) > 1:
        for i in range(1, len(hist_10y)):
            if hist_10y[i] < hist_10y[i-1] * 0.99:
                cut_count += 1
    max_div = np.max(div_history)
    rec_progress = current_div / max_div if max_div and max_div > 0 else 1.0
    
    ni_ttm = None
    if rows[-1][2]:
        ni_ttm = float(rows[-1][2])
        
    facts = DividendFacts(
        asset_id='HK:STOCK:03968',
        dividends_ttm=current_div,
        net_income_ttm=ni_ttm,
        dps_5y_mean=mean_5y,
        dps_5y_std=std_5y,
        cut_years_10y=cut_count,
        dividend_recovery_progress=rec_progress
    )
    
    div_info = evaluate_dividend_safety(facts)
    print("Dividend Facts:", facts)
    print("Dividend Info:", div_info)

