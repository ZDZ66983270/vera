# 通用企业财报关键词映射配置
# 用于PDF解析时的关键词匹配（非银行企业）

# 通用企业关键词（适用于制造业、科技、消费等）
GENERIC_KEYWORDS = {
    
    #######################################################
    # 1. 资产负债表 (Balance Sheet – Core)
    #######################################################
    
    "total_assets": [
        ["截至报告期末，资产总额", "截至报告期末，资产总计", "报告期末，资产总额"],
        ["资产总额", "资产总计", "总资产", "Total assets", "Total Assets"]
    ],
    
    "total_liabilities": [
        ["截至报告期末，负债总额", "截至报告期末，负债合计", "报告期末，负债总额"],
        ["负债总额", "负债合计", "总负债", "Total liabilities", "Total Liabilities"]
    ],
    
    "common_equity_end": [
        ["期末股东权益合计", "期末归属于母公司股东权益", "归属于母公司所有者权益"],
        ["股东权益合计", "所有者权益合计", "Total equity", "Shareholders' equity"]
    ],
    
    "cash_and_equivalents": [
        # 优先：现金流量表期末余额
        ["期末现金及现金等价物余额", "期末现金及现金等价物"],
        # 次优：资产负债表
        ["货币资金", "现金及现金等价物", "Cash and cash equivalents"]
    ],
    
    "total_debt": [
        ["有息负债合计", "总借款", "借款总额", "债务总额"],
        ["短期借款与长期借款合计", "Total debt", "Total borrowings"]
    ],
    
    
    #######################################################
    # 2. 利润表 (Income Statement – Core Earnings)
    #######################################################
    
    "revenue": [
        ["报告期内，实现营业收入", "报告期内营业收入", "本期营业收入"],
        ["营业收入", "主营业务收入", "营业总收入", "Revenue", "Total revenue"]
    ],
    
    "net_income_attributable_to_common": [
        ["归属于母公司股东的净利润", "归属于母公司所有者的净利润", "归母净利润"],
        ["Net income attributable to shareholders", "Net profit attributable to owners"]
    ],
    
    "gross_profit": [
        ["毛利", "销售毛利", "毛利润"],
        ["Gross profit", "Gross margin"]
    ],
    
    "r_and_d_expense": [
        ["研发费用", "研究开发费用", "研发支出"],
        ["R&D expenses", "Research and development expenses"]
    ],
    
    "operating_profit": [
        ["营业利润", "经营利润"],
        ["Operating profit", "Operating income", "EBIT"]
    ],
    
    "ebit": [
        ["息税前利润", "EBIT"],
        ["Earnings before interest and tax"]
    ],
    
    "interest_expense": [
        ["利息费用", "利息支出", "财务费用"],
        ["Interest expense", "Finance costs"]
    ],
    
    "non_recurring_profit": [
        ["非经常性损益", "营业外收支净额", "一次性损益"],
        ["Non-recurring items", "Extraordinary items"]
    ],
    
    
    #######################################################
    # 3. 现金流与投资 (Cashflow & Capex)
    #######################################################
    
    "operating_cashflow": [
        ["经营活动产生的现金流量净额", "经营活动所产生的现金流量净额", "经营活动现金流量净额"],
        ["经营性现金流净额", "Operating cash flows", "Cash from operations"]
    ],
    
    "capex": [
        ["购建固定资产、无形资产和其他长期资产支付的现金", "资本性支出"],
        ["购置固定资产支付的现金", "Capital expenditures", "Capex"]
    ],
    
    "free_cashflow": [
        ["自由现金流", "Free cash flow", "FCF"]
        # 通常计算得出：operating_cashflow - capex
    ],
    
    "dividends_paid_cashflow": [
        ["分配股利、利润或偿付利息支付的现金", "支付股利支付的现金"],
        ["已支付股利", "Dividends paid", "Cash dividends paid"]
    ],
    
    "share_buyback_amount": [
        ["回购股份支付的现金", "购买库存股支付的现金"],
        ["股份回购", "Share repurchase", "Treasury stock purchases"]
    ],
    
    
    #######################################################
    # 4. 营运资本 (Working Capital – Core Signals)
    #######################################################
    
    "accounts_receivable_end": [
        ["应收账款期末余额", "应收账款"],
        ["Accounts receivable", "Trade receivables"]
    ],
    
    "inventory_end": [
        ["存货期末余额", "存货"],
        ["Inventory", "Inventories"]
    ],
    
    "accounts_payable_end": [
        ["应付账款期末余额", "应付账款"],
        ["Accounts payable", "Trade payables"]
    ],
    
    
    #######################################################
    # 5. 每股与股本结构 (Per-share & Capital Structure)
    #######################################################
    
    "eps": [
        ["基本每股收益", "每股收益", "EPS"],
        ["Basic earnings per share", "Earnings per share"]
    ],
    
    "shares_outstanding_common_end": [
        ["期末普通股总股数", "期末股本总额", "股本合计", "期末总股本"],
        ["Total shares outstanding", "Common shares outstanding"]
    ],
    
    "dividend_per_share": [
        ["每股股利", "每股分红", "每股现金股利"],
        ["Dividend per share", "DPS", "Cash dividend per share"]
    ],
}


def get_generic_keywords(metric: str) -> list:
    """
    获取通用企业指定指标的关键词列表
    
    Args:
        metric: 指标名称，如 "revenue"
    
    Returns:
        关键词组列表
    """
    return GENERIC_KEYWORDS.get(metric, [])
