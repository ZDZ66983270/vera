from analysis.quality_assessment import build_quality_snapshot
from dataclasses import dataclass

@dataclass
class MockFundamentals:
    industry: str = "Technology"
    net_profit_ttm: float = 100.0
    revenue_ttm: float = 1000.0
    pe_ttm: float = 15.0
    pb_ratio: float = 2.0
    debt_to_equity: float = 0.5
    dividend_yield: float = 0.03
    buyback_ratio: float = 0.01
    revenue_history: list = None
    roe: float = 0.15
    net_margin: float = 0.10

@dataclass
class MockBankMetrics:
    core_tier1_capital_ratio: float = 0.13
    provision_expense: float = 10.0
    total_loans: float = 1000.0
    net_interest_income: float = 50.0
    net_fee_income: float = 20.0
    roe: float = 0.14
    npl_balance: float = 5.0
    overdue_90_loans: float = 4.0
    provision_coverage: float = 2.8

def test_general():
    print("\n--- Testing General Template (Tech) ---")
    f = MockFundamentals()
    f.revenue_history = [800, 850, 900, 1000]
    
    snapshot = build_quality_snapshot("TEST:TECH", f)
    print(f"Level: {snapshot.quality_buffer_level}")
    print(f"Template: {snapshot.quality_template_name}")
    print(f"Summary: {snapshot.quality_summary}")
    for flag, val in vars(snapshot).items():
        if "flag" in flag:
            print(f"  {flag}: {val}")

def test_bank():
    print("\n--- Testing Bank Template ---")
    f = MockFundamentals(industry="Bank")
    # roe/cet1/nii are merged from bank_metrics in our builder
    b = MockBankMetrics()
    
    snapshot = build_quality_snapshot("TEST:BANK", f, bank_metrics=b)
    print(f"Level: {snapshot.quality_buffer_level}")
    print(f"Template: {snapshot.quality_template_name}")
    print(f"Summary: {snapshot.quality_summary}")
    for flag, val in vars(snapshot).items():
        if "flag" in flag:
            print(f"  {flag}: {val}")

if __name__ == "__main__":
    test_general()
    test_bank()
