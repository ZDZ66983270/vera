
import akshare as ak
try:
    df = ak.stock_financial_hk_analysis_indicator_em(symbol="00998", indicator="年度") 
    print("Columns:", df.columns)
    print(df[['REPORT_DATE', 'BASIC_EPS', 'EPS_TTM']].head(10))

except Exception as e:
    print(f"Error: {e}")
