# vera/mappings.py

# U_state Mappings
U_STATE_CN = {
    "U1_UPTREND": "上升趋势",
    "U2_RANGE": "区间震荡",
    "U3_DISCOVERY": "价值发现",
    "U4_STABILIZATION": "止跌企稳",
    "U5_REVERSAL": "反转确认",
    "UNKNOWN": "未知阶段"
}

# Detailed Definitions for Tooltips
U_STATE_DEFINITIONS_CN = {
    "U1_UPTREND": "价格处于明确的上升通道，均线多头排列，市场情绪乐观。做多胜率较高，重点关注回调买入机会。",
    "U2_RANGE": "价格在特定区间内上下波动，无明确方向。多空力量均衡，适合在箱体边缘进行高抛低吸，不仅要看价格还要看成交量变化。",
    "U3_DISCOVERY": "价格脱离原区间寻找新平衡，通常伴随剧烈波动和放量。市场分歧巨大，风险极高，建议观望等待新结构形成。",
    "U4_STABILIZATION": "经过大幅下跌或波动后，抛压逐渐衰竭，波动率收敛。虽然趋势尚未反转，但下行空间有限，是左侧布局的潜在窗口。",
    "U5_REVERSAL": "价格突破关键阻力位或均线压制，底部形态确立。趋势由跌转升，是右侧交易的最佳切入点。",
    "UNKNOWN": "由于数据不足或特征不明显，无法识别当前市场结构。"
}

# O_state Mappings
O_STATE_CN = {
    "O1_IV_EXPANSION": "IV 膨胀",
    "O2_PLATEAU": "IV 高位钝化",
    "O3_IV_CRUSH": "IV 坍塌",
    "UNKNOWN": "IV 未知"
}

O_STATE_DEFINITIONS_CN = {
    "O1_IV_EXPANSION": "隐含波动率快速上升，往往对应市场恐慌或重大事件前夕。期权价格昂贵，买方风险增加，卖方需防范波动率进一步冲高。",
    "O2_PLATEAU": "隐含波动率维持高位，市场恐慌情绪持续但未进一步恶化。此时期权价格依然较高，需警惕事件落地后的IV回落风险。",
    "O3_IV_CRUSH": "隐含波动率快速回落，通常发生在事件落地或恐慌消退后。期权价格大幅缩水，对期权买方极度不利，利好期权卖方。",
    "UNKNOWN": "缺少期权数据或隐含波动率特征不明显。"
}

# R_state Mappings (Verdict)
R_STATE_CN = {
    "RED": "禁止操作",
    "YELLOW": "观察/轻仓",
    "GREEN": "允许交易",
    "UNKNOWN": "无法裁定"
}

# Action Prompts (Next Conditions)
ACTION_PROMPTS_CN = {
    "no_new_low_1d": "需连续 1 日不创新低",
    "no_new_low_2d": "需连续 2 日不创新低",
    "vol_ratio < 1.5": "成交量需回归常态 (<1.5x)",
    "iv_down_2d": "IV 需连续 2 日回落",
    "close_pos > 0.55": "收盘需站上当日区间 55%",
    "Price discovery phase": "处于价格发现剧烈波动期",
    "Stabilization phase": "处于止跌企稳观察期",
    "Reversal/Range with IV crush": "反转/震荡且 IV 回落窗口",
    "Transition state": "处于过渡状态"
}

def get_u_state_cn(state):
    return U_STATE_CN.get(state, state)

def get_u_state_def(state):
    return U_STATE_DEFINITIONS_CN.get(state, "暂无定义")

def get_o_state_cn(state):
    return O_STATE_CN.get(state, state)

def get_o_state_def(state):
    return O_STATE_DEFINITIONS_CN.get(state, "暂无定义")

def get_r_state_cn(state):
    return R_STATE_CN.get(state, state)

def get_action_cn(condition):
    # Try exact match first
    if condition in ACTION_PROMPTS_CN:
        return ACTION_PROMPTS_CN[condition]
    # Simple heuristic fallback if not mapped
    return condition
