
import sys
import os
import pandas as pd
from datetime import datetime

# Add project root to path
sys.path.append(os.getcwd())

from data.price_cache import load_price_series
from analysis.risk_matrix import build_risk_card
from metrics.risk_engine import RiskEngine

def debug_hsbc_risk():
    asset_id = "00005.HK"
    as_of_date = datetime.now().strftime("%Y-%m-%d")
    
    print(f"--- Debugging Risk Card for {asset_id} as of {as_of_date} ---")
    
    # 1. Load Prices
    start_date = (datetime.now() - pd.DateOffset(years=10)).strftime("%Y-%m-%d")
    df = load_price_series(asset_id, start_date, as_of_date)
    if df.empty:
        print("Error: No price data found.")
        return

    print(f"Loaded {len(df)} price records.")
    current_price = df.iloc[-1]['close']
    print(f"Current Price: {current_price}")
    
    # Ensure DatetimeIndex
    if 'trade_date' in df.columns:
        df['trade_date'] = pd.to_datetime(df['trade_date'])
        df = df.set_index('trade_date').sort_index()

    # 2. Run Risk Engine
    # RiskEngine is static and expects a Series
    metrics = RiskEngine.calculate_risk_metrics(df['close'])
    metrics['report_date'] = as_of_date
    print("\n[RiskMetrics Output]")
    print(f"drawdown_state: {metrics.get('drawdown_state')}")
    print(f"risk_state: {metrics.get('risk_state')}")
    
    # 3. Build Risk Card
    # We pass empty market_context for now as we focus on individual property
    card = build_risk_card(
        asset_id=asset_id,
        current_price=current_price,
        risk_metrics=metrics,
        as_of_date=as_of_date,
        snapshot_id="DEBUG_001"
    )
    
    print("\n[RiskCard Output]")
    print(f"d_state: {card.get('d_state')}")
    print(f"path_risk_level: {card.get('path_risk_level')}")
    print("-" * 30)

if __name__ == "__main__":
    debug_hsbc_risk()
