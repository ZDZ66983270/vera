
import pandas as pd
from metrics.risk_engine import RiskEngine

def test_d_state():
    print("--- Testing D-State Logic ---")
    
    # Case 1: D0 (Stable) - Price near peak
    prices_d0 = pd.Series([100, 105, 108, 110, 109], index=pd.date_range("2023-01-01", periods=5))
    print("\nCase 1: D0 Expectation")
    RiskEngine.calculate_path_risk_state(prices_d0)
    
    # Case 2: D3 (Deep DD) - Price dropped significantly
    prices_d3 = pd.Series([100, 80, 60, 50, 55], index=pd.date_range("2023-01-01", periods=5))
    print("\nCase 2: D3 Expectation")
    RiskEngine.calculate_path_risk_state(prices_d3)
    
    # Case 3: D6 (Recovered) - Dropped and came back (Old 80% case)
    # Price 90 (Peak 100, Trough 50). Rec = (90-50)/50 = 80%. Should be D5 now.
    prices_d6_old = pd.Series([100, 50, 60, 80, 90], index=pd.date_range("2023-01-01", periods=5))
    print("\nCase 3a: D5 Expectation (Rec 80%, was D6)")
    RiskEngine.calculate_path_risk_state(prices_d6_old)

    # Case 4: D6 New (Rec >= 95%)
    # Price 98. Rec = 96%
    prices_d6_new = pd.Series([100, 50, 60, 80, 98], index=pd.date_range("2023-01-01", periods=5))
    print("\nCase 4: D6 Expectation (Rec 96%)")
    RiskEngine.calculate_path_risk_state(prices_d6_new)
    
    # Case 5: New High
    prices_high = pd.Series([100, 50, 60, 80, 105], index=pd.date_range("2023-01-01", periods=5))
    print("\nCase 5: New High Expectation")
    RiskEngine.calculate_path_risk_state(prices_high)

if __name__ == "__main__":
    test_d_state()
