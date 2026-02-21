
import pandas as pd
from metrics.drawdown import recovery_progress, max_drawdown_details

# 1. Simulate Price Data (Volatile Asset like TSLA)
# Peak at 100 on day 10
# Valley at 50 on day 20 (50% DD)
# Current at 75 on day 30 (50% recovered)
# Peak = 100, Valley = 50, Diff = 50
# Current = 75, (75-50)/50 = 0.5 (50%)

dates = pd.date_range(start="2023-01-01", periods=30)
prices = [10] * 10       # Flat start
prices.append(100)       # Day 10: Peak (idx 10)
prices.extend([90, 80, 70, 60, 55, 52, 51, 50, 50]) # Decline to 50
# Now at index 19
# Recovery phase
prices.extend([55, 60, 65, 70, 75, 75, 75, 75, 75, 75])

s = pd.Series(prices, index=dates)

print("--- Data Simulation ---")
print(f"Peak Price: {s.max()} (should be 100)")
print(f"Current Price: {s.iloc[-1]} (should be 75)")

# 2. Test Recovery Progress
progress = recovery_progress(s)
print(f"\nCalculated Recovery Progress: {progress:.2f}")

# 3. Verify Logic
expected = (75 - 50) / (100 - 50)
print(f"Expected Progress: {expected:.2f}")

if abs(progress - expected) < 1e-6:
    print("\n✅ Verification SUCCESS: Logic matches expected calculation.")
else:
    print(f"\n❌ Verification FAILED: {progress} != {expected}")

# 4. Check Status Label Derivation (Python-side check of UI logic)
status = "Unknown"
if progress < 0.30: status = "尚处深度回撤"
elif progress < 0.70: status = "部分修复"
elif progress < 0.95: status = "大部分修复"
else: status = "视作已修复"

print(f"Derived UI Status: {status} (Expected: 部分修复)")
