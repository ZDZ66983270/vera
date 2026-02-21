# vera/explain/counter_evidence_defs.py

def get_checklist_for_state(d_state: str) -> dict:
    """
    返回特定状态下的反证清单（Counter-evidence Checklist）
    用于审计当前状态是否已经接近失效或处于边界。
    """
    
    # D3: 深度博弈 (Deep Game/Trough)
    if d_state == "D3":
        return {
            "state": "D3",
            "title": "D3「深度博弈」反证审计",
            "subtitle": "若以下项勾选过多，说明风险释放动能已衰减，资产可能正向 D4 转移或由于波动消失而失效。",
            "items": [
                {
                    "id": "D3_VOLATILITY_DOWNSHIFT",
                    "label": "波动率出现系统性回落",
                    "definition": "短期波动率（如 20D HV）显著脱离历史 90% 分位点，进入中低位。",
                    "meaning": "D3 的核心是“恐慌/强平”导致的极端波动。如果波动消失，博弈可能已转入僵持期。"
                },
                {
                    "id": "D3_VOLUME_DRYUP",
                    "label": "成交量出现极度缩量",
                    "definition": "日成交量低于 5 日均量的 50%，且价格维持窄幅震荡。",
                    "meaning": "说明强制抛压已出尽，但也缺乏承接盘。D3 状态正在“阴跌化”而非“博弈化”。"
                },
                {
                    "id": "D3_CORRELATION_DECOUPLING",
                    "label": "与大盘相关性异常脱钩",
                    "definition": "市场剧烈反弹时，该资产独跌，或市场平稳时该资产出现独立无量下坠。",
                    "meaning": "可能存在非公开的基本面坍塌，抵消了结构性底部的支撑。"
                }
            ],
            "rules": {
                "boundary_threshold": 2,
                "boundary_warning": "【审计预警】检测到多个 D3 反证信号。当前状态可能已接近失效边界，底部逻辑正在被削弱，请警惕“僵尸底”。"
            }
        }

    # D4: 早期反弹 (Early Rebound)
    if d_state == "D4":
        return {
            "state": "D4",
            "title": "D4「早期反弹」反证审计",
            "subtitle": "用于评估当前反弹是“结构重启”还是单纯的“超跌抽风”。",
            "items": [
                {
                    "id": "D4_FAIL_TO_HOLD_VALLEY",
                    "label": "跌破本轮 MDD 谷底价格",
                    "definition": "价格重新跌回并收盘于本轮最大回撤的最低点位之下。",
                    "meaning": "反弹被证伪。结构重新陷入 D3 且下行空间再次打开。"
                },
                {
                    "id": "D4_ZERO_MOMENTUM_ALPHA",
                    "label": "超额收益 (Alpha) 显著为负",
                    "definition": "在反弹窗口期，涨幅显著低于板块 ETF 或对应市场指数（β）。",
                    "meaning": "反映跟风盘极少，主力资金未回场。此类 D4 极易演变为“二次探底”。"
                }
            ],
            "rules": {
                "boundary_threshold": 1,
                "boundary_warning": "【审计预警】D4 反证信号触发。当前反弹极度脆弱，结构性支撑尚未形成，请防范“诱多”风险。"
            }
        }

    # D5: 中期修复 (Mid-term Recovery)
    if d_state == "D5":
        return {
            "state": "D5",
            "title": "D5「中期修复」反证审计",
            "subtitle": "评估修复是否进入阻力区或出现“假修复”。",
            "items": [
                {
                    "id": "D5_RESISTANCE_REJECTION",
                    "label": "关键阻力位（上部区域）放量冲高回落",
                    "definition": "在接近修复进度 60%-70% 处出现长上影线且成交量翻倍。",
                    "meaning": "上方解套盘抛压远超预期，修复动能可能在 D5 阶段性枯竭。"
                },
                {
                    "id": "D5_RSI_NEGATIVE_DIVERGENCE",
                    "label": "价格创新高但动量指标背离",
                    "definition": "价格点位在修复，但 RSI 或其他动能指标的高点在降低。",
                    "meaning": "属于“缩量修复”，缺乏坚实的基本面支撑，易发生踩踏式回调。"
                }
            ],
            "rules": {
                "boundary_threshold": 1,
                "boundary_warning": "【审计预警】D5 修复动能出现衰减信号。资产可能在进入 D6 前遭遇剧烈阻力，建议重新校准仓位期望。"
            }
        }

    # Default fallback
    return {
        "state": d_state,
        "title": "是否存在反证？",
        "subtitle": "（该状态暂无专属反证清单，仅作通用合规检查）",
        "items": [
            {
                "id": "GENERIC_NO_DATA",
                "label": "基础数据是否存在关键缺失？",
                "definition": "财报、价格或核心指标是否依赖过时/缺失的数据？",
                "meaning": "数据质量直接影响状态判定的可审计性。"
            }
        ],
        "rules": {
            "boundary_threshold": 1,
            "boundary_warning": "当前状态审计数据受限，请结合多源信息辅助决策。"
        }
    }
