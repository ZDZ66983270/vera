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

---

## 第四部分：VERA 2.0 风险体系演进 (Risk Structure 2.0)

> **重大更新**：VERA 2.0 完成了从“数值风险”向“感知风险”的工程闭环，引入了 2x2 风险矩阵与自省护栏。

### 1. 鲁棒的风险历史状态机 (Historical Risk Path)
*   **设计原则**：采用 D0-D6 状态机。为消除随机噪音，引入了 **7 天确认期** 机制（即新状态必须连续满足 7 天且风险环境未极端恶化才由系统确认）。
*   **Backfill (回填) 逻辑**：分析引擎在首次处理新资产时，会自动追溯并持久化过去 200 个交易日的路径状态，解决了冷启动下的趋势观察断层。
*   **风险事件探测**：系统自动记录 `SECONDARY_DRAWDOWN`（反弹失败触底）等 3 类历史风险核爆点。
*   **实现位置**：`metrics/state_machine.py` + `drawdown_state_history` 表。

### 2. VERA 2.0 2×2 风险坐标矩阵
风险不再是一个分数，而是一个 **空间坐标 (X, Y)**。
*   **维度 X (Position Risk)**：现在贵吗？
    *   **核心指标**：`price_percentile` (10年价格分位)。
*   **维度 Y (Path Risk)**：过程稳吗？
    *   **核心指标**：`volatility_percentile` (波动率分位) + `drawdown_stage` (回撤深度解析)。
*   **四大象限 (Quadrant)**：
    *   **Q1 (追涨区)**: 高位 + 低路径风险。
    *   **Q2 (泡沫区)**: 高位 + 高路径风险。
    *   **Q3 (恐慌区)**: 低位 + 高路径风险。
    *   **Q4 (稳态区)**: 低位 + 低路径风险。

### 3. 行为护栏 (Behavior Flags)
这是 VERA 最核心的“自省能力”。系统根据象限自动触发风险标记：
*   **FOMO_RISK (Q1)**：警示过度乐观与追涨欲望。
*   **OVERCONFIDENCE_RISK (Q2)**：警示情绪化决策可能性。
*   **PANIC_SELL_RISK (Q3)**：警示生理性恐慌导致的错误杀跌。
*   **FALSE_SECURITY_RISK (Q4)**：警示警觉性由于环境温和而下降。

### 4. 风险承受力自评 (Risk Profiling)
*   **千人千面**：利用 5 题问卷（得分 0-10）映射至**保守、均衡、进取**三种画像。
*   **动态展示**：画像直接影响 RiskCard 的话术深度、警示敏感度以及警报框的视觉强度。
*   **实现位置**：`analysis/risk_profile.py` + `user_risk_profiles` 表。

### 5. 数据导入与开放平台能力
*   **批量 CSV 识别**：支持单文件多标的（Multi-symbol）自动识别与原子化入库，通过 `utils/csv_handler.py` 驱动。
*   **闭环存储**：所有 RiskCard 快照（`risk_card_snapshot`）均包含触发时的系统上下文，支持未来进行 AI 辅助的自省分析。

---

## 第五部分：最新系统架构全景与数据底座 (System Architecture & Data Foundation - 2025-12-22)

### 1. 最新物理目录结构 (2025-12-22)
```text
.
├── analysis/           # 核心分析逻辑 (矩阵计算、画像映射、估值引擎)
│   ├── risk_matrix.py  # VERA 2.0 坐标系与象限判定
│   ├── risk_profile.py # 风险自评问卷与用户画像等级
│   ├── dashboard.py    # 仪表盘 ViewModel 生成核心
│   └── valuation.py    # 估值锚点选择与 trap 检测
├── engine/             # 任务编排层
│   └── snapshot_builder.py # 自动化分析快照生成器 (核心大脑)
├── data/               # 数据获取与持久化缓存
│   ├── price_cache.py  # SQLite 行情读写隔离层
│   ├── fetch_marketdata.py # Yahoo Finance/AkShare 接口对接
│   └── fetch_fundamentals.py # 财务基础数据抓取
├── metrics/            # 原子计算模块 (纯函数)
│   ├── state_machine.py # 风险路径状态机核心 (D0-D6)
│   ├── drawdown.py      # 回撤与恢复期算法
│   └── volatility.py    # 波动率计算逻辑
├── db/                 # 存储体系
│   ├── schema.sql      # 数据库全量 DDL 定义
│   └── connection.py   # 数据库连接池与会话管理
├── utils/              # 支撑工具集
│   ├── csv_handler.py  # 灵活的 CSV 行情导入适配
│   └── stock_name_fetcher.py # 资产名称智能识别引擎
├── docs/               # 深度文档与解释
│   └── risk_path_explanation.md # 风险路径状态深度白皮书
└── app.py              # VERA Streamlit 语义化交互前端
```

### 2. 最新数据库表结构体系 (Data Models)
| 表名 | 类别 | 核心功能说明 |
| :--- | :--- | :--- |
| `assets` | 基础层 | 标的注册中心，存储代码、行业与市场归属 |
| `vera_price_cache` | 数据层 | 行情主快照，支持去重增量存储与多源适配 |
| `financial_history` | 数据层 | 存储 EPS/BPS 及银行股专项资产质量指标 |
| `analysis_snapshot` | 计算层 | **分析锚点**，锁定特定时刻的风险、估值与结论 |
| `drawdown_state_history` | 路径层 | 记录 D0-D6 状态转移全轨迹，包含确认期逻辑 |
| `risk_card_snapshot` | 判断层 | 存储 VERA 2.0 2x2 矩阵坐标及象限解读快照 |
| `behavior_flags` | 预警层 | 关联特定快照的行为认知标记 (如 FOMO, Panic) |
| `user_risk_profiles` | 画像层 | 存储用户风险偏好得分及个性化 UI 展示配置 |
| `risk_events` | 事件层 | 记录状态机触发的关键风险转移事件 (如崩塌、修复失败) |
