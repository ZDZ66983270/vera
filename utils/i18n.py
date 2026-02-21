# utils/i18n.py
"""
VERA 系统中英文翻译模块
提供代码层英文标识符到用户友好的中英文显示转换
"""

TRANSLATIONS = {
    # D-states (个股回撤状态)
    "D0": "未形成完整回撤结构",
    "D1": "正常波动期",
    "D2": "结构中性",
    "D3": "深度博弈",
    "D4": "早期反弹",
    "D5": "中期修复",
    "D6": "大部分修复",
    
    # I-states (指数回撤状态)
    "I0": "未形成完整回撤结构",
    "I1": "正常波动期",
    "I2": "结构中性",
    "I3": "博弈区",
    "I4": "敏感阶段",
    "I5": "脆弱阶段",
    "I6": "深度危机",
    
    # Path Risk Levels
    "LOW": "低风险",
    "MID": "中性",
    "HIGH": "高风险",
    
    # Position Zones
    "Peak": "阶段高点",
    "Upper": "上部区域",
    "Middle": "中部区域",
    "Lower": "下部区域",
    "Trough": "阶段低点",
    "Unknown": "未知",
    
    # Market Regime Labels
    "Healthy Differentiation": "健康分化",
    "Systemic Compression": "系统性压缩",
    "Systemic Stress": "系统性压力",
    "Crisis Mode": "危机模式",
    "Selective Market": "选择性市场",
    
    # Amplification Levels
    "Low": "低",
    "Medium": "中等",
    "High": "高",
    "Extreme": "极端",
    
    # Alpha Headroom
    "None": "无",
    
    # Sector Alignment
    "aligned": "同步",
    "negative_divergence": "负向偏离",
    "positive_divergence": "正向偏离",
    
    # Volatility Regime
    "STABLE": "稳定",
    "ELEVATED": "升高",
    "VOLATILE": "波动",
    
    # Valuation Status
    "Overvalued": "高估",
    "Undervalued": "低估",
    "Fair": "合理",
    "Premium": "高估",
    "Discount": "低估",

    # GICS Sectors
    "Energy": "能源",
    "Materials": "原材料",
    "Industrials": "工业",
    "Consumer Discretionary": "可选消费",
    "Consumer Staples": "必需消费",
    "Health Care": "医疗保健",
    "Financials": "金融",
    "Information Technology": "信息技术",
    "Communication Services": "通信服务",
    "Utilities": "公用事业",
    "Real Estate": "房地产",

    # HK Sectors (Custom)
    "HK Tech Leaders": "港股科技龙头",
    "HK Blue Chips": "港股蓝筹",

    # Market Indices
    "^GSPC": "标普500",
    "^NDX": "纳斯达克100",
    "^DJI": "道琼斯工业",
    "HSI": "恒生指数",
    "HSTECH": "恒生科技",
    "000300": "沪深300",
    
    # Quality Levels
    "STRONG": "强",
    "MODERATE": "中等",
    "WEAK": "弱",
}


def translate(key: str, format: str = "bilingual") -> str:
    """
    翻译英文代码为中文或中英双语显示
    
    Args:
        key: 英文标识符 (如 "D2", "HIGH", "Peak")
        format: 显示格式
            - "bilingual": 中英双语 "D2 (结构中性)"
            - "zh_only": 仅中文 "结构中性"
            - "en_only": 仅英文 "D2"
    
    Returns:
        格式化后的字符串
    """
    if key is None:
        return "-"
    
    zh = TRANSLATIONS.get(str(key), None)
    
    if format == "zh_only":
        return zh if zh else str(key)
    elif format == "en_only":
        return str(key)
    elif format == "bilingual":
        if zh:
            return f"{key} ({zh})"
        else:
            return str(key)
    else:
        return str(key)


def get_translation(key: str) -> str:
    """
    获取纯中文翻译（快捷方法）
    
    Args:
        key: 英文标识符
    
    Returns:
        中文翻译，如不存在则返回原key
    """
    return TRANSLATIONS.get(str(key), str(key))


def get_legend_text(category: str, format: str = "text") -> str:
    """
    生成完整的 Tooltip 图例说明
    
    Args:
        category: 类别 ("D_STATE", "I_STATE", "PATH_RISK", "VOL_REGIME")
        format: "text" (纯文本) 或 "html" (富文本)
        
    Returns:
        格式化的图例字符串
    """
    is_html = (format == "html")
    
    # Helper for formatting
    def _b(text): return f"<strong>{text}</strong>" if is_html else text
    def _ul(items):
        if is_html:
            lis = "".join([f"<li>{item}</li>" for item in items])
            return f"<ul>{lis}</ul>"
        else:
            return "\n\n".join([f"• {item}" for item in items])
            
    if category == "D_STATE":
        header = "个股状态定义 (D-States):"
        items = [
            f"{_b('D0 (未形成结构)')}: 历史数据不足或处于绝对高点",
            f"{_b('D1 (正常波动)')}: 回撤 < 15%",
            f"{_b('D2 (结构中性)')}: 回撤 15-25%，多空平衡",
            f"{_b('D3 (深度博弈)')}: 回撤 > 35%，处于谷底博弈区",
            f"{_b('D4 (早期反弹)')}: 出现触底反弹 (Recovery > 0%)，但仍脆弱",
            f"{_b('D5 (中期修复)')}: 修复进度 > 30%，脱离最危险区域",
            f"{_b('D6 (大部分修复)')}: 修复进度 > 95%，结构重启但未创新高"
        ]
        return f"{_b(header)}<br><br>{_ul(items)}" if is_html else f"{header}\n\n{_ul(items)}"

    elif category == "I_STATE":
        header = "指数状态定义 (I-States):"
        items = [
            f"{_b('I0 (未形成结构)')}: 处于历史高点附近",
            f"{_b('I1 (正常波动)')}: 回撤 < 10%",
            f"{_b('I2 (结构中性)')}: 回撤 10-20%",
            f"{_b('I3 (博弈区)')}: 回撤 20-30%",
            f"{_b('I4 (敏感阶段)')}: 回撤 30-45%",
            f"{_b('I5 (脆弱阶段)')}: 回撤 45-60%",
            f"{_b('I6 (深度危机)')}: 回撤 > 60%"
        ]
        return f"{_b(header)}<br><br>{_ul(items)}" if is_html else f"{header}\n\n{_ul(items)}"

    elif category == "PATH_RISK":
        header = "路径结构风险 (Path Risk):"
        desc = "基于回撤状态 (D-State) 的结构化风险映射："
        items = [
            f"{_b('LOW (低风险)')}: 对应 D0/D1/D6。底部结构扎实或处于强势区间，上涨阻力较小。",
            f"{_b('MID (中性)')}: 对应 D2/D3。处于中间区域，存在一定套牢盘，多空博弈为主。",
            f"{_b('HIGH (高风险)')}: 对应 D4/D5。处于反弹敏感区或脆弱修复期，上方临近密集套牢区，阻力较大。"
        ]
        if is_html:
            return f"{_b(header)}<br>{desc}<br><br>{_ul(items)}"
        else:
            return f"{header}\n\n{desc}\n\n{_ul(items)}"

    elif category == "VOL_REGIME":
        header = "波动体制 (Volatility Regime):"
        items = [
            f"{_b('STABLE (稳定)')}: 波动率低于历史中枢，市场情绪平稳，适合顺势交易。",
            f"{_b('ELEVATED (升高)')}: 波动率开始放大，市场出现分歧，建议降低仓位。",
            f"{_b('VOLATILE (剧烈)')}: 极高波动，市场恐慌或狂热，风险收益比极差。"
        ]
        return f"{_b(header)}<br><br>{_ul(items)}" if is_html else f"{header}\n\n{_ul(items)}"
        
    elif category == "R_STATE":
        header = "近期周期定义 (R-States, 1Y):"
        desc = "基于最近 1 年回撤幅度 (相对于波动率) 与持续时间的综合评估："
        items = [
            f"{_b('R0 (正常波动)')}: 价格运行平稳，无显著超预期回撤压力。",
            f"{_b('R1 (短期回落)')}: 出现常规小幅回落，属于良性技术性调整。",
            f"{_b('R2 (结构性回调)')}: 回撤强度适中，卖压开始倾向于结构化展示。",
            f"{_b('R3 (深度调整)')}: 市场情绪显著恶化，回撤已超出常规二倍波动范围。",
            f"{_b('R4 (极端危机)')}: 极端抛售压力，常对应流动性变差或基本面剧变。"
        ]
        if is_html:
            return f"{_b(header)}<br>{desc}<br><br>{_ul(items)}"
        else:
            return f"{header}\n\n{desc}\n\n{_ul(items)}"
            
    elif category == "VOLATILITY_1Y":
        header = "年化波动率 (Volatility, 1Y):"
        desc = "衡量资产过去一年的价格波动强度（年化标准差）："
        items = [
            f"反映资产的波动特性，是计算风险回撤敏感度的核心基准。",
            f"高波动资产通常伴随更高的预期收益，但也意味着更深的常规波动区间。",
            f"若回撤幅度远超波动率（> 2σ），通常暗示基本面转向或流动性冲击。"
        ]
        if is_html: return f"{_b(header)}<br>{desc}<br><br>{_ul(items)}"
        else: return f"{header}\n\n{desc}\n\n{_ul(items)}"

    elif category == "REL_MDD":
        header = "相对历史最大回撤 (Relative MDD):"
        desc = "反映当前回撤强度在过去 10 年历史长河中的所处位置："
        items = [
            f"{_b('0%')}: 资产处于（或接近）历史最高点，无回撤压力。",
            f"{_b('50%')}: 当前回撤已达到历史最大回撤的一半，通常进入强心理支撑区。",
            f"{_b('100%')}: 当前正经历过去 10 年来最极端的抛售压力（最大回撤）。",
            f"本指标通过对比历史“最差情况”，帮助您快速判断当前回撤是否已处于历史大底级别。"
        ]
        if is_html: return f"{_b(header)}<br>{desc}<br><br>{_ul(items)}"
        else: return f"{header}\n\n{desc}\n\n{_ul(items)}"

    elif category == "QUALITY_FIREWALL":
        header = "数据质量防火墙 (Data Quality Firewall):"
        desc = "自动检测是否存在亏损、财务异常及严重估值缺失，确保估值参考有效性："
        items = [
            f"{_b('亏损/微利检测')}: 净利润为负或无法计算 PE，导致估值模型失真。",
            f"{_b('财务异常波动')}: 核心指标出现非线性的剧烈跳变，可能暗示重组或非经常性损益干扰。",
            f"{_b('数据严重缺失')}: 缺乏足够的历史 TTM 数据支撑长周期分位点回测。",
            f"{_b('陷阱预警')}: 若本项检测【不通过】，则下方的“价值分位点”可能失效，甚至形成“估值陷阱”。"
        ]
        if is_html: return f"{_b(header)}<br>{desc}<br><br>{_ul(items)}"
        else: return f"{header}\n\n{desc}\n\n{_ul(items)}"
            
    return ""
