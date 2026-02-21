# VERA WALKTHROUGH.md (修订版)

> **定位**：这是给 **未来的你** 以及 **AI 开发协作者** 看的文档。
> 它不是营销文档，不追求“完成感”，而是追求 **可持续的正确性**。

---

## 第一部分：核心定义

### 1. 项目定位
VERA 是一个 **“投资价值与风险结构认知系统”**。
*   ❌ 不是交易系统
*   ❌ 不是荐股系统
*   ❌ 不是实时行情软件

**核心目标**：
*   **冻结判断**：在特定时刻锁定认知，防止后视镜偏见。
*   **追踪风险结构变化**：关注风险的构成，而非单一数值。
*   **约束决策行为**：通过系统化的规则对抗人性的弱点。

### 2. 核心原则 (Core Principles)
1.  **Snapshot First (快照优先)**
    所有分析必须基于可回溯的 `snapshot`（快照），而非实时计算。历史是不可变的，认知也应被记录。
2.  **Separation of Concerns (关注点分离)**
    行情、指标、风险、结论必须严格分层，互不干扰。
3.  **Risk Is Structural, Not Scalar (风险是结构)**
    风险不是一个分数（Score），而是一组结构关系（Structure）。
4.  **No Implicit Action (无隐式指令)**
    系统不生成任何“买 / 卖 / 持有”的直接指令，只提供决策依据。

### 3. 数据流总览
```mermaid
graph TD
    External[External Data] --> PriceCache[price_cache (行情唯一真源)]
    PriceCache --> Snapshot[vera_snapshot (指标与状态冻结)]
    Snapshot --> RiskCard[risk_card_snapshot (风险结构判断)]
    RiskCard --> Flags[behavior_flags (行为/认知压力标记)]
    Flags --> View[长期视图 / 对比分析]
```

### 4. 关于“分析日当天行情”的明确说明
**分析日当天行情**：
*   仅用于定位当前价格状态（如：当前是否在谷底）。
*   **不参与** 历史分位数、回撤、波动率计算。
*   **不影响** 已冻结 snapshot 的任何结论。
> **目的**：这是防止系统被“即时波动污染”的保险丝，确保长期视角的稳定性。

### 5. 引擎说明 (Engine Status)
当前实现包含以下引擎的 `v0.x` 版本：
*   **Risk Engine**: 路径风险 & 位置风险
*   **Valuation Engine**: 估值区间与相对状态
*   **Trap Engine**: 结构陷阱 & 行为陷阱
*   **Conclusion Engine**: 非指令型总结

**注意**：所有引擎都是可替换、可版本化的，当前代码不视为最终实现。

### 6. 引擎输出版本化
每一次 `RiskCard` 输出必须包含以下元数据，否则无法复盘：
*   `engine_name`
*   `engine_version`
*   `rule_version`
*   `snapshot_id`
*   `generated_at`

### 7. 前端使用约束
前端系统（Dashboard/App）：
*   只能读取 `snapshot` 与聚合结果。
*   **禁止** 触发任何重新计算。
*   **禁止** 隐式刷新行情。
*   **禁止** 提供参数调优入口。
> VERA 是“认知冻结系统”，不是参数优化的探索沙盒。

### 8. 明确禁止事项
VERA 明确 **不支持**：
*   🚫 不同资产 RiskCard 的直接排名。
*   🚫 使用单一 RiskScore 代替结构判断。
*   🚫 将 RiskCard 作为自动买卖信号。
*   🚫 用收益表现验证系统优劣。

### 9. 当前状态声明
当前版本为 **VERA v0.x**：
*   实现了最小可运行闭环 (MVP)。
*   所有结论均为“结构性提示”。
*   系统设计仍处于可演进阶段。

---

## 第二部分：架构红线 (Architectural Red Lines)

🚨 **这是你未来重构、加功能、接 AI 时的“宪法”，不可违背。**

### 🔴 Red Line 1：禁止实时 Recompute 历史风险
任何历史风险指标（最大回撤、波动率、分位数）都只能在 `snapshot` 生成时计算并持久化。
*   ❌ **禁止** 前端或分析模块即时重算。

### 🔴 Red Line 2：禁止行情源绕过 price_cache
`price_cache` 是行情的 **唯一入口**。
*   ❌ **禁止** 任何模块直接访问外部行情 API (yfinance/tushare 等)。
*   **后果**：否则你将失去可复现性、数据一致性和审计能力。

### 🔴 Red Line 3：禁止“结论覆盖结构”
`Conclusion` 永远是附属层。
*   ❌ **禁止** 反向修改 Risk / Valuation / Trap 的原始结果。
*   **认知**：结论 ≠ 真理，结论只是当时的解释尝试。

### 🔴 Red Line 4：禁止 Risk 指标被压缩为一个“好/坏”
任何 UI / API / 文档都不得把风险表达为：
*   ❌ 单一分数
*   ❌ 红绿灯
*   ❌ 简单评级
> **风险是结构，不是标签。** （例如：高波动不等于高风险，可能是高赔率）

### 🔴 Red Line 5：禁止系统给出“行为建议”
VERA **不回答**：
*   “该不该买？”
*   “该不该卖？”
*   “现在是否安全？”
它只回答：**“你现在处于什么风险结构下？”**

### 🔴 Red Line 6：禁止用收益验证系统正确性
VERA 的成功标准 **不是收益**，而是：
*   ✅ 是否提前识别了风险积累？
*   ✅ 是否减少了结构性的认知误判？

### 🔴 Red Line 7：禁止无版本号的“逻辑升级”
任何引擎逻辑的变化：
*   ✅ 必须更新 `version`。
*   ✅ 必须保留旧 `snapshot` 的原始判断。
*   **后果**：否则历史数据会被“篡改”，复盘将失去意义。

---

> **写在最后**
>
> 你已经不是在“写一个投资工具”了，你是在给自己造一个 **长期不会骗你的系统**。
>
> 多数系统的失败，不是算错指标，而是：
> 1. 忘了自己当初为什么这么设计。
> 2. 被“看起来更聪明”的功能慢慢腐蚀。
>
> 现在你把这两份东西立住，VERA 未来怎么扩展，都不会走歪。

---
---

## 第三部分：技术实现参考 (v0.x MVP)

> **说明**：以下内容为 MVP 阶段的具体技术实现细节存档，供开发参考。

### 1. 已创建的目录结构
```tree
vera/
├── main.py                     # ✅ 程序入口
├── config.py                   # ✅ 全局配置
├── requirements.txt            # ✅ 依赖项
│
├── db/
│   ├── __init__.py
│   ├── connection.py           # ✅ 仅支持 SQLite
│   └── schema.sql              # ✅ 仅 2 张表
│
├── data/
│   ├── __init__.py
│   ├── fetch_marketdata.py     # ✅ 基础数据获取
│   └── price_cache.py          # ✅ 缓存读写（地基）
│
├── analysis/
│   ├── __init__.py
│   └── price_series.py         # ✅ PriceSeries 类
│
├── metrics/
│   ├── __init__.py
│   ├── drawdown.py             # ✅ 纯函数
│   ├── volatility.py           # ✅ 纯函数
│   └── tail_risk.py            # ✅ 纯函数
│
├── engine/
│   ├── __init__.py
│   └── snapshot_builder.py     # ✅ 系统核心
│
└── utils/
│   ├── __init__.py
│   ├── market_calendar.py      # ✅ 占位符
│   └── logger.py               # ✅ 基础日志
```

### 2. 核心实现细节

#### 2.1 数据库模式
九张表（3 张旧表 + 6 张新表）：

**Phase 2 基础表**：
- `assets` - 资产表
- `price_history` - 价格历史表
- `financial_history` - 财务历史表 (含银行股专属字段)

**Phase 3 核心分析表**：
- `analysis_snapshot` - 分析快照表（核心，UUID 主键）
- `metric_details` - 指标明细表
- `decision_log` - 决策日志表

#### 2.2 风险计算引擎 (Risk Engine)
封装在 `metrics/risk_engine.py`，100% 可测试：
1. `max_drawdown` - 最大回撤
2. `current_drawdown` - 当前回撤
3. `annual_volatility` - 年化波动率
4. `recovery_time` - 恢复时间
5. `worst_n_day_drop` - 最差 n 日跌幅

#### 2.3 估值与陷阱引擎
- **Valuation Engine**: 自动选择 PE/PB/PS (亏损->PS, 银行/地产->PB, 默认->PE)。
- **Trap Engine**: 
    - 通用陷阱：高股息 + 负增长 + 高估值。
    - 银行专属陷阱 ("假净资产")：不良偏离度 > 120% 或 拨备覆盖率 < 130%。
    - 价值兑现评分 (-2 ~ +2)。

#### 2.4 统一结论生成器 (Conclusion Engine)
- **Hard Stop**: 回撤/波动超标 -> "不适合"
- **银行逻辑**: 评分 >= 1 (高质量) + 低估 -> "适合长期持有 (安全垫厚)"

### 3. 已解决问题 (Fixed) ✅
1. **最大回撤计算窗口**：
   - **调整**：将风险计算的数据窗口设定为 **10 年**。
   - **逻辑**：既避免了 30 年前过于久远的市场环境干扰，又能有效捕捉近期的主要周期性风险（如 2015, 2018, 2022 等）。

### 4. 总结
✅ **MVP 完成** - 所有必需文件已创建，系统可端到端执行。
✅ **原则落地** - 实现了快照机制、纯函数指标计算、以及行业特定的深度分析逻辑。
