import pandas as pd
import numpy as np
from metrics.risk_engine import RiskEngine

def simulate_prices():
    # Simulate a price drop: 100 -> 110 -> 80
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    prices = pd.Series([100, 102, 105, 108, 110, 105, 100, 95, 90, 80], index=dates)
    return prices

def test_reverted_logic():
    print("Testing Reverted D-State Logic (Single Layer)...")
    
    prices = simulate_prices()
    res = RiskEngine.calculate_path_risk_state(prices, mdd_total=-0.35, mdd_duration_days=10)
    
    state = res['state']
    desc = res['desc']
    dd_node = res['drawdown']
    
    print(f"\nScenario: Deep Pullback")
    print(f"  State: {state} (Expected: D2 or D3)")
    print(f"  Desc: {desc}")
    print(f"  MDD Duration: {dd_node['mdd_duration_days']} (Expected: 10)")
    print(f"  Current DD: {dd_node['current_dd_pct']:.1%}")
    
    # Check if primary/overlay keys are GONE
    if 'd_state_primary' in res:
        print("  Error: d_state_primary still exists!")
    else:
        print("  Success: 3-layer structure removed.")
        
    # Scenario 2: N=5 Protection
    dates_n5 = pd.date_range("2024-01-01", periods=10, freq="D")
    prices_n5 = pd.Series([100, 101, 102, 103, 104, 103.5, 103, 102.5, 102, 101], index=dates_n5)
    
    metrics_6 = RiskEngine.calculate_risk_metrics(prices_n5.iloc[:6])
    print(f"\nScenario 2 (N=5 Protection - 1 day after peak):")
    print(f"  Reported Current DD: {metrics_6['current_drawdown']:.1%} (Expected: 0.0%)")
    
    metrics_10 = RiskEngine.calculate_risk_metrics(prices_n5)
    print(f"Scenario 2 (N=5 Protection - 5+ days after peak):")
    print(f"  Reported Current DD: {metrics_10['current_drawdown']:.1%} (Expected: < 0%)")

if __name__ == "__main__":
    test_reverted_logic()
