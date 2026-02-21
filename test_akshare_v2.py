
import akshare as ak

symbol = "600030"

print("--- Testing Sina Financials ---")
try:
    df = ak.stock_financial_report_sina(stock=symbol, symbol="利润表")
    print("Sina columns:", df.columns)
    print(df.head(2))
except Exception as e:
    print(f"Sina Failed: {e}")

print("\n--- Testing EM Profit Sheet ---")
try:
    # 东方财富-利润表-按报告期
    # stock_lrb_em or similar?
    # Let's check available attributes starting with stock_financial... or stock_lrb...
    pass
except:
    pass
    
# Listing candidates
print("\n--- Candidate APIs ---")
candidates = [m for m in dir(ak) if "financial" in m or "lrb" in m]
print(candidates[:10]) 
