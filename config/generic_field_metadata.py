# 通用企业字段元数据配置
# 定义每个字段的属性和特征

GENERIC_FIELD_METADATA = {
    
    #######################################################
    # 1. 资产负债表 (Balance Sheet)
    #######################################################
    
    "total_assets": {
        "label_zh": "资产总额",
        "label_en": "Total Assets",
        "category": "balance_sheet",
        "required": True,
        "is_large": True,
        "ttm_required": False,  # 资产负债表为时点数据
        "positive_only": True,
        "unit_hint": "百万元"
    },
    
    "total_liabilities": {
        "label_zh": "负债总额",
        "label_en": "Total Liabilities",
        "category": "balance_sheet",
        "required": True,
        "is_large": True,
        "ttm_required": False,
        "positive_only": True,
        "unit_hint": "百万元"
    },
    
    "common_equity_end": {
        "label_zh": "期末股东权益",
        "label_en": "Shareholders' Equity (End)",
        "category": "balance_sheet",
        "required": True,
        "is_large": True,
        "ttm_required": False,
        "positive_only": True,
        "unit_hint": "百万元"
    },
    
    "cash_and_equivalents": {
        "label_zh": "现金及现金等价物",
        "label_en": "Cash and Cash Equivalents",
        "category": "balance_sheet",
        "required": True,
        "is_large": True,
        "ttm_required": False,
        "positive_only": True,
        "unit_hint": "百万元"
    },
    
    "total_debt": {
        "label_zh": "有息负债总额",
        "label_en": "Total Debt",
        "category": "balance_sheet",
        "required": True,
        "is_large": True,
        "ttm_required": False,
        "positive_only": True,
        "unit_hint": "百万元"
    },
    
    
    #######################################################
    # 2. 利润表 (Income Statement)
    #######################################################
    
    "revenue_ttm": {
        "label_zh": "营业收入（TTM）",
        "label_en": "Revenue (TTM)",
        "category": "income_statement",
        "required": True,
        "is_large": True,
        "ttm_required": True,
        "positive_only": True,
        "unit_hint": "百万元"
    },
    
    "net_income_attributable_to_common_ttm": {
        "label_zh": "归母净利润（TTM）",
        "label_en": "Net Income Attributable to Common (TTM)",
        "category": "income_statement",
        "required": True,
        "is_large": True,
        "ttm_required": True,
        "positive_only": False,  # 可能为负（亏损）
        "unit_hint": "百万元"
    },
    
    "gross_profit_ttm": {
        "label_zh": "毛利（TTM）",
        "label_en": "Gross Profit (TTM)",
        "category": "income_statement",
        "required": True,
        "is_large": True,
        "ttm_required": True,
        "positive_only": False,
        "unit_hint": "百万元",
        "calculation": "revenue_ttm - cost_of_sales_ttm"
    },
    
    "r_and_d_expense_ttm": {
        "label_zh": "研发费用（TTM）",
        "label_en": "R&D Expense (TTM)",
        "category": "income_statement",
        "required": False,  # 非所有企业都有研发
        "is_large": True,
        "ttm_required": True,
        "positive_only": True,
        "unit_hint": "百万元"
    },
    
    "operating_profit_ttm": {
        "label_zh": "营业利润（TTM）",
        "label_en": "Operating Profit (TTM)",
        "category": "income_statement",
        "required": True,
        "is_large": True,
        "ttm_required": True,
        "positive_only": False,
        "unit_hint": "百万元"
    },
    
    "ebit_ttm": {
        "label_zh": "息税前利润 EBIT（TTM）",
        "label_en": "EBIT (TTM)",
        "category": "income_statement",
        "required": True,
        "is_large": True,
        "ttm_required": True,
        "positive_only": False,
        "unit_hint": "百万元"
    },
    
    "interest_expense_ttm": {
        "label_zh": "利息费用（TTM）",
        "label_en": "Interest Expense (TTM)",
        "category": "income_statement",
        "required": False,
        "is_large": True,
        "ttm_required": True,
        "positive_only": True,
        "unit_hint": "百万元"
    },
    
    "non_recurring_profit_ttm": {
        "label_zh": "非经常性损益（TTM）",
        "label_en": "Non-recurring Items (TTM)",
        "category": "income_statement",
        "required": False,
        "is_large": True,
        "ttm_required": True,
        "positive_only": False,
        "unit_hint": "百万元"
    },
    
    
    #######################################################
    # 3. 现金流与投资 (Cashflow & Capex)
    #######################################################
    
    "operating_cashflow_ttm": {
        "label_zh": "经营活动现金流净额（TTM）",
        "label_en": "Operating Cash Flow (TTM)",
        "category": "cashflow",
        "required": True,
        "is_large": True,
        "ttm_required": True,
        "positive_only": False,
        "unit_hint": "百万元"
    },
    
    "capex_ttm": {
        "label_zh": "资本性支出 Capex（TTM）",
        "label_en": "Capital Expenditures (TTM)",
        "category": "cashflow",
        "required": True,
        "is_large": True,
        "ttm_required": True,
        "positive_only": True,
        "unit_hint": "百万元"
    },
    
    "free_cashflow_ttm": {
        "label_zh": "自由现金流（TTM）",
        "label_en": "Free Cash Flow (TTM)",
        "category": "cashflow",
        "required": True,
        "is_large": True,
        "ttm_required": True,
        "positive_only": False,
        "unit_hint": "百万元",
        "calculation": "operating_cashflow_ttm - capex_ttm"
    },
    
    "dividends_paid_cashflow": {
        "label_zh": "已支付股利（现金流口径）",
        "label_en": "Dividends Paid (Cash Flow)",
        "category": "cashflow",
        "required": True,
        "is_large": True,
        "ttm_required": True,
        "positive_only": True,
        "unit_hint": "百万元"
    },
    
    "share_buyback_amount_ttm": {
        "label_zh": "股份回购金额（TTM）",
        "label_en": "Share Buyback Amount (TTM)",
        "category": "cashflow",
        "required": False,
        "is_large": True,
        "ttm_required": True,
        "positive_only": True,
        "unit_hint": "百万元"
    },
    
    
    #######################################################
    # 4. 营运资本 (Working Capital)
    #######################################################
    
    "accounts_receivable_end": {
        "label_zh": "应收账款期末余额",
        "label_en": "Accounts Receivable (End)",
        "category": "working_capital",
        "required": False,
        "is_large": True,
        "ttm_required": False,
        "positive_only": True,
        "unit_hint": "百万元"
    },
    
    "inventory_end": {
        "label_zh": "存货期末余额",
        "label_en": "Inventory (End)",
        "category": "working_capital",
        "required": False,
        "is_large": True,
        "ttm_required": False,
        "positive_only": True,
        "unit_hint": "百万元"
    },
    
    "accounts_payable_end": {
        "label_zh": "应付账款期末余额",
        "label_en": "Accounts Payable (End)",
        "category": "working_capital",
        "required": False,
        "is_large": True,
        "ttm_required": False,
        "positive_only": True,
        "unit_hint": "百万元"
    },
    
    
    #######################################################
    # 5. 每股与股本结构 (Per-share & Capital Structure)
    #######################################################
    
    "eps_ttm": {
        "label_zh": "每股收益 EPS（TTM）",
        "label_en": "Earnings Per Share (TTM)",
        "category": "per_share",
        "required": True,
        "is_large": False,
        "ttm_required": True,
        "positive_only": False,
        "unit_hint": "元/股"
    },
    
    "shares_outstanding_common_end": {
        "label_zh": "期末普通股股本",
        "label_en": "Common Shares Outstanding (End)",
        "category": "per_share",
        "required": True,
        "is_large": False,  # 股数通常以"股"为单位
        "ttm_required": False,
        "positive_only": True,
        "unit_hint": "股"
    },
    
    "dividend_per_share": {
        "label_zh": "每股股利（TTM）",
        "label_en": "Dividend Per Share (TTM)",
        "category": "per_share",
        "required": False,
        "is_large": False,
        "ttm_required": True,
        "positive_only": True,
        "unit_hint": "元/股"
    },
}


def get_field_metadata(field_name: str) -> dict:
    """
    获取指定字段的元数据
    
    Args:
        field_name: 字段名称
    
    Returns:
        字段元数据字典
    """
    return GENERIC_FIELD_METADATA.get(field_name, {})


def get_required_fields() -> list:
    """获取所有必需字段列表"""
    return [
        field for field, meta in GENERIC_FIELD_METADATA.items()
        if meta.get("required", False)
    ]


def get_ttm_fields() -> list:
    """获取所有需要TTM计算的字段列表"""
    return [
        field for field, meta in GENERIC_FIELD_METADATA.items()
        if meta.get("ttm_required", False)
    ]


def get_fields_by_category(category: str) -> list:
    """
    按分类获取字段列表
    
    Args:
        category: 分类名称（balance_sheet/income_statement/cashflow等）
    
    Returns:
        该分类下的字段列表
    """
    return [
        field for field, meta in GENERIC_FIELD_METADATA.items()
        if meta.get("category") == category
    ]
