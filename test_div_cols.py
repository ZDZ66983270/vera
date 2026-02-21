
import akshare as ak
try:
    df_div = ak.stock_fhps_detail_em(symbol="600030")
    print("Dividend Columns:", df_div.columns)
    print(df_div.head(2))
except Exception as e:
    print(e)
