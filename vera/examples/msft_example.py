# vera/examples/msft_example.py

import pandas as pd
import numpy as np
from datetime import datetime
from vera.engines.underlying_regime_engine import UnderlyingRegimeEngine
from vera.engines.options_state_engine import OptionsStateEngine
from vera.engines.permission_engine import PermissionEngine

def create_mock_data():
    """
    Creates mock data simulating a "Discovery" (U3) phase for MSFT
    """
    dates = pd.date_range(end=datetime.today(), periods=100, freq='B')
    
    # Mock Price: Uptrend then crash
    prices = [100.0]
    for i in range(1, 90):
        prices.append(prices[-1] * (1 + np.random.normal(0.001, 0.01))) # Drift up
    for i in range(90, 100):
        if i == 95:
            prices.append(prices[-1] * 0.92) # Big drop (-8%)
        else:
            prices.append(prices[-1] * (1 + np.random.normal(-0.005, 0.02))) # Volatile down
            
    df = pd.DataFrame(index=dates, data={"close": prices})
    df["open"] = df["close"] * (1 + np.random.normal(0, 0.005))
    df["high"] = df[["open", "close"]].max(axis=1) * (1 + abs(np.random.normal(0, 0.01)))
    df["low"] = df[["open", "close"]].min(axis=1) * (1 - abs(np.random.normal(0, 0.01)))
    df["volume"] = np.random.randint(1000000, 5000000, size=len(df))
    # Spike volume on crash
    df.iloc[95, df.columns.get_loc("volume")] = 15000000 
    
    df["ret"] = df["close"].pct_change()
    df["vol_ma20"] = df["volume"].rolling(20).mean()
    
    # Mock IV: Rising then plateau
    iv_base = 0.20
    ivs = []
    for i in range(100):
        if i > 90:
            iv_base += 0.02 # Rise
        ivs.append(iv_base + np.random.normal(0, 0.01))
    
    iv_series = pd.Series(data=ivs, index=dates)
    
    return df, iv_series

def run_example():
    print("--- VERA Engine Demo: MSFT Mock Scenario ---")
    
    # 1. Prepare Data
    price_df, iv_series = create_mock_data()
    
    # 2. Instantiate Engines
    u_engine = UnderlyingRegimeEngine()
    o_engine = OptionsStateEngine()
    p_engine = PermissionEngine()

    # 3. Evaluate State
    u_out = u_engine.evaluate(price_df)
    o_out = o_engine.evaluate(iv_series)

    # 4. Get Permission
    decision = p_engine.evaluate(
        U_state=u_out["U_state"],
        O_state=o_out["O_state"]
    )

    # 5. Output Result
    result = {
        "timestamp": datetime.now().isoformat(),
        "underlying": u_out,
        "options": o_out,
        "decision": decision
    }
    
    import json
    print(json.dumps(result, indent=2, default=str))
    
    return result

if __name__ == "__main__":
    run_example()
