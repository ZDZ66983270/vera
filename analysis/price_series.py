class PriceSeries:
    def __init__(self, df):
        self.df = df
        self.closes = df["close"].values
        self.returns = df["close"].pct_change().dropna().values
