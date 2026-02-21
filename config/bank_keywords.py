# 银行财报关键词映射配置
# 用于PDF解析时的关键词匹配

# 通用关键词（适用于大多数银行）
COMMON_KEYWORDS = {
    # 资产负债表 - 规模
    "total_assets": [
        ["截至报告期末，资产总额", "截至报告期末，资产总计", "报告期末，资产总额", "报告期末，资产总计"],
        ["报告期末资产总额", "报告期末资产总计", "本集团资产总额", "资产总额", "资产总计", "总资产", "Total assets"]
    ],
    
    "total_liabilities": [
        ["截至报告期末，负债总额", "截至报告期末，负债合计", "报告期末，负债总额", "报告期末，负债合计"],
        ["负债总额", "负债合计", "总负债", "Total liabilities"],
        ["各项负债", "负债总计"]
    ],
    
    # 利润表 - 收入与利润
    "revenue": [
        ["报告期内，实现营业收入", "报告期内，营业收入", "报告期内实现营业收入"],
        ["本集团实现营业收入", "本集团营业收入", "营业收入", "营业净收入", "实现的营业收入", "主营业务收入", "Revenue", "Total Operating Income"]
    ],
    
    "net_profit": [
        ["归属于本行股东的净利润", "归属于上市公司股东的净利润", "归母净利润"],
        ["净利润", "Profit for the period"]
    ],
    
    "net_interest_income": [
        ["报告期内，实现利息净收入", "报告期内，利息净收入", "报告期实现利息净收入"],
        ["本集团实现利息净收入", "本集团利息净收入", "利息净收入", "净利息收入", "Net interest income"]
    ],
    
    "net_fee_income": [
        ["报告期内，实现手续费及佣金净收入", "报告期内容，手续费及佣金净收入"],
        ["本集团实现手续费及佣金净收入", "手续费及佣金净收入", "净手续费及佣金收入", "Fee and commission income"],
        ["手续费收入", "手续费佣金净收入", "非利息收入", "中间业务收入"]
    ],
    
    "provision_expense": [
        ["信用减值损失", "资产减值损失", "Credit impairment losses"],
        ["计提信用减值", "计提资产减值", "减值损失"]
    ],
    
    # 资产质量
    "total_loans": [
        ["发放贷款及垫款总额", "贷款和垫款总额", "贷款和垫款", "贷款总额"],
        ["客户贷款和垫款", "发放贷款和垫款", "Gross loans"],
        ["客户贷款", "贷款余额"]
    ],
    
    "loan_loss_allowance": [
        ["贷款减值准备余额", "贷款损失准备", "Loan loss allowance"],
        ["贷款减值准备", "减值准备合计", "拨备余额"]
    ],
    
    "npl_balance": [
        ["不良贷款余额", "不良贷款额"],
        ["不良贷款"]
    ],
    
    "npl_ratio": [
        ["不良贷款率", "不良率", "NPL ratio"]
    ],
    
    "provision_coverage": [
        ["拨备覆盖率", "拨备率", "Provision coverage"]
    ],
    
    # 资本与权益
    "core_tier1_ratio": [
        ["核心一级资本充足率", "CET1 capital ratio"],
        ["核心一级资本充足"]
    ],
    
    "common_equity_begin": [
        ["期初股东权益合计", "期初归属于母公司股东权益"]
    ],
    
    "common_equity_end": [
        ["期末股东权益合计", "期末归属于母公司股东权益", "归属于本行股东权益"]
    ],
    
    # 股票数据
    "eps": [
        ["基本每股收益", "每股收益", "EPS", "Basic earnings per share"],
        ["归属于本行普通股股东的基本每股收益"]
    ],
    
    "shares_outstanding": [
        ["期末普通股总股数", "期末股本总额", "股本合计", "股本"]
    ],
    
    "dividends_paid": [
        ["已支付股利", "Dividends paid"]
    ],
    
    "dividend_per_share": [
        ["每股股利", "每股分红", "Dividend per share", "DPS"],
        ["每10股派发现金红利", "派发现金红利", "现金分红"]
    ],
    
    # 现金流与债务
    "operating_cashflow": [
        ["经营活动产生的现金流量净额", "经营活动所产生的现金流量净额", "经营活动现金流量净额"],
        ["本集团经营活动产生的现金流量净额", "经营活动净现金流", "经营性现金流净额", "Operating cash flows"]
    ],
    
    "cash_and_equivalents": [
        # 优先匹配：期末余额（现金流量表最后一行）
        ["期末现金及现金等价物余额", "期末现金及现金等价物", "期末现金及等价物余额"],
        # 次优先：资产负债表中的现金项
        ["货币资金", "现金及存放中央银行款项", "存放中央银行款项"],
        # 最后：宽泛匹配（但会被上面的优先级覆盖）
        # 注意：不要匹配"汇率变动对现金及现金等价物的影响"
        ["现金及现金等价物", "Cash and cash equivalents"]
    ],
    
    "total_debt": [
        ["有息负债合计", "总借款", "借款总额", "债务总额", "计息负债", "计息负债余额"],
        ["Total debt", "Total borrowings", "Interest-bearing debt", "Interest bearing liabilities"]
    ],

    "short_term_debt": [
        ["短期借款", "一年内到期的长期借款"],
        ["Short-term borrowings"]
    ],
    
    "long_term_debt": [
        ["长期借款", "长期负债"],
        ["Long-term borrowings"]
    ]
}

# 银行特定关键词映射（覆盖或扩展通用关键词）
BANK_SPECIFIC_KEYWORDS = {
    # 招商银行 (CN:STOCK:600036, HK:03968)
    "CMB": {
        "total_loans": [
            ["贷款和垫款总额", "貸款和墊款總額"],  # 招行特有表述
            ["客户贷款和垫款总额"],
        ],
        "net_profit": [
            ["归属于本行股东的净利润"],
        ],
        "net_fee_income": [
            ["手续费及佣金净收入"],
            ["净手续费及佣金收入"],  # 明确匹配 "净手续费及佣金收入286.95亿"
        ]
    },
    
    # 工商银行 (CN:STOCK:601398, HK:01398)
    "ICBC": {
        "total_loans": [
            ["发放贷款和垫款", "發放貸款和墊款"],
            ["客户贷款及垫款"],
        ]
    },
    
    # 建设银行 (CN:STOCK:601939, HK:00939)
    "CCB": {
        "total_loans": [
            ["发放贷款和垫款净额"],
            ["客户贷款"],
        ]
    },
    
    # 中国银行 (CN:STOCK:601988, HK:03988)
    "BOC": {
        "total_loans": [
            ["客户贷款及垫款"],
            ["发放贷款及垫款"],
        ]
    },
    
    # 农业银行 (CN:STOCK:601288, HK:01288)
    "ABC": {
        "total_loans": [
            ["发放贷款和垫款"],
            ["客户贷款总额"],
        ]
    },
    
    # 交通银行 (CN:STOCK:601328, HK:03328)
    "BOCOM": {
        "total_loans": [
            ["发放贷款及垫款"],
        ]
    }
}

# 银行代码到简称的映射
BANK_CODE_MAPPING = {
    "CN:STOCK:600036": "CMB",
    "HK:03968": "CMB",
    "CN:STOCK:601398": "ICBC",
    "HK:01398": "ICBC",
    "CN:STOCK:601939": "CCB",
    "HK:00939": "CCB",
    "CN:STOCK:601988": "BOC",
    "HK:03988": "BOC",
    "CN:STOCK:601288": "ABC",
    "HK:01288": "ABC",
    "CN:STOCK:601328": "BOCOM",
    "HK:03328": "BOCOM",
}


def get_keywords_for_bank(asset_id: str, metric: str) -> list:
    """
    获取特定银行和指标的关键词列表
    
    Args:
        asset_id: 资产ID，如 "CN:STOCK:600036"
        metric: 指标名称，如 "total_loans"
    
    Returns:
        关键词组列表
    """
    # 获取银行简称
    bank_code = BANK_CODE_MAPPING.get(asset_id)
    
    # 先获取通用关键词
    keywords = COMMON_KEYWORDS.get(metric, [])
    
    # 如果有银行特定关键词，优先使用
    if bank_code and bank_code in BANK_SPECIFIC_KEYWORDS:
        bank_keywords = BANK_SPECIFIC_KEYWORDS[bank_code].get(metric)
        if bank_keywords:
            # 银行特定关键词放在前面（优先匹配）
            keywords = bank_keywords + keywords
    
    return keywords
