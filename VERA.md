🌐 VERA 开发总纲（给编程 AI）

你是 VERA（Value & Risk Assessment System） 的专职开发助手。
任何修改都必须优先保证：金融含义正确 > 风险提示清晰 > 代码整洁可维护 > 视觉漂亮。
本工程所有对话、实施方案均必须使用中文。

⸻

0. 系统使命（永远不要忘记）
	1.	VERA 的核心任务：
	•	用 历史回撤 + 波动 + 估值 + 质量 + 行为，给出 可行动 的资产风险/价值评估；
	•	为实盘决策服务，宁可少说也不能乱说。
	2.	VERA 不是短线交易系统，而是：
	•	以 10 年周期风险视角 + 1 年近期动态 为主的风控/资产配置助手；
	•	重点是「承受多大的回撤，换来怎样的收益与安全边际」。

⸻

1. 架构与分层原则
	1.	严格保持三层分离：
	•	数据层（SQLite / ETL）：只存 事实（价格、财报、因子…），不得出现 current_ 这类语义字段；
	•	引擎层（Python backend）：只做计算逻辑、状态机、规则引擎；
	•	展示层（Streamlit / 前端）：只做渲染和文案，不埋业务逻辑。
	2.	所有规则、阈值、状态映射必须：
	•	写在 YAML / config（如 vera_rules.yaml、quality_templates/*.yaml）；
	•	前后端都禁止写死「魔法数字」阈值（例如 20% 回撤、80% 修复等）。
	3.	任何新增功能：
	•	优先考虑「能否复用现有指标/状态机」；
	•	不能破坏原有字段含义（兼容 > 重构）。

⸻

2. 数据与指标：绝对禁止随意更改定义

2.1 价格 / 回撤 / 波动
	1.	所有价格取 复权收盘价（若有），否则收盘价。
	2.	Max Drawdown / 当前回撤 必须采用统一定义：
	•	任意日期 t 的当前回撤：
\text{DD}_t = \frac{P_t - \max_{s \le t} P_s}{\max_{s \le t} P_s}
	3.	年化波动率 Volatility, 1y：
	•	使用 最近 252 个交易日 日收益率的标准差 × √252；
	•	日收益率用对数收益或简单收益只能二选一，选定后全局一致，并写入文档。
	4.	回撤周期：
	•	长期：10Y MaxDD（10y_max_dd），用于 D-state；
	•	近期：1Y 回撤 & 天数（off_high_1y, days_since_1y_high），用于 R-state。

2.2 估值密度（PE / PB）
	1.	PE_TTM 统一公式：
PE_{TTM} = \frac{\text{当前股价}}{\text{EPS}_{TTM}}
	2.	对于仅有稀疏 PE/PB 点（FMP、百度等），必须使用「基本面锚点」逻辑：
	•	先用价格和报告期 PE/PB 反推 Implied EPS/BPS；
	•	在报告期之间 forward-fill EPS/BPS；
	•	再用每日收盘价 / EPS/BPS 生成连续日度 PE/PB 曲线。
	3.	估值状态 禁止只看一个当日 PE 点：
	•	必须基于 历史分位（N 年 PE 分布）计算百分位；
	•	再通过 YAML 映射到「深度低估 / 低估 / 合理 / 高估 / 深度高估」。

⸻

3. 风险引擎 & 状态机（红线区）

3.1 D-State：长期风险结构（10Y）
	1.	D-State 代表 从历史大坑里爬出来的程度。
典型分层（可在 YAML 配阈值）：
	•	D0：无明显回撤 / 刚起跌；
	•	D1：早期回撤；
	•	D2：结构性回调；
	•	D3：深度回撤；
	•	D4：反弹早期；
	•	D5：修复中段；
	•	D6：完全修复（从这轮 MaxDD 坑里爬完）。
	2.	必须显式计算：
	•	10y_max_dd：过去 10 年最大回撤；
	•	current_dd_10y：相对于 10 年高点的当前回撤；
	•	recovery_rate（回撤修复率）：
\text{recovery\_rate} = 1 - \frac{|\text{current\_dd\_10y}|}{|\text{10y\_max\_dd}|}
	3.	禁止让 D-State 与 R-State 混用同一字段；
	•	D-State 看「长期坑 + 修复进度」；
	•	R-State 看「近 1 年波动和回撤」。

3.2 R-State：近期路径风险（1Y）
	1.	R-State（R0~R3 等）基于：
	•	off_high_1y：近 1 年内相对高点的当前回撤；
	•	days_since_1y_high：距离 1 年内高点过去多少天；
	•	波动率 vol_1y 与历史均值对比；
	2.	目标：
	•	把「同样是 D5 修复中段」，区分为「近期又跌了一波」还是「近期震荡健康」。

3.3 PermissionEngine（动作权限）
	1.	所有「买入/卖出/滚动」的建议，只能由 PermissionEngine 输出；
	2.	PermissionEngine 的输入：
	•	U_state：标的价格结构（U1–U5 等）；
	•	O_state：期权波动状态（O1–O3）；
	•	D/R 状态、估值状态可作为补充。
	3.	红灯规则（必须保留）：
	•	若处于「价格发现/恐慌杀跌」（例如 U3_DISCOVERY），强制 RED；
	•	任何时候，只要 PermissionEngine 给出 RED，前端必须显示「禁止操作」。

⸻

4. 质量模板 & 财报规则

4.1 模板分类
	1.	质量模板最少包含两类：
	•	banks：银行/金融机构；
	•	platform / generic：互联网平台 / 普通企业。
	2.	模板选择原则：
	•	优先根据板块/行业字段（如 Financials + Banks → banks 模板）；
	•	支持用户手动覆盖（某只资产可强制绑定特定模板）。

4.2 Banks 模板关键指标（必须支持）
从财报/监管披露中至少支持以下原始字段（英文字段名必须稳定）：
	•	利润表：
	•	interest_income, interest_expense, net_interest_income_raw
	•	fee_and_commission_income, fee_and_commission_expense, net_fee_income_raw
	•	provision_for_credit_losses
	•	net_income_attributable_to_common
	•	资产负债表：
	•	gross_loans, loan_loss_reserve
	•	npl_balance 或 npl_ratio_raw
	•	total_common_equity_begin, total_common_equity_end
	•	监管披露：
	•	core_tier1_capital_ratio_raw（或从 CET1/RWA 推导）
	•	股本 & 分红：
	•	shares_outstanding_common_end
	•	dividends_paid_cashflow, dividends_declared_common, dividend_per_share

不得更改这些字段语义。
所有派生指标（ROE、信贷成本、拨备覆盖率、资本缓冲等）必须由引擎计算。

⸻

5. UI / UX 规范（Risk Overlay & Deep Dive）
	1.	风险来源对照（Risk Overlay） 卡片结构固定：
	•	顶部：D-状态 + 路径风险标签 (高/中/低)；
	•	中部（长期）：10Y MaxDD + 起止日期 + 持续时间；
	•	中部（深度风险）：年化波动率 + 相对历史最大回撤；
	•	下部（近期）：R-State + 当前回撤 + 距 1 年高点天数 + 历史分位；
	2.	深度风险模块（Deep Dive）应包括：
	•	Volatility, 1y（本标的、板块、大盘对比）；
	•	Relative History Max Drawdown 的色条（0–100% 分位）。
	3.	文案规则：
	•	遵循「标题一句话说明 + 数字 + 短解释」；
	•	所有缩写（DD, Vol, PB…）必须提供 Tooltip 解释。

⸻

6. 命名与数据库约束
	1.	数据表只用语义清晰的字段名：
	•	✅ close, pe_ttm, pb, eps_ttm, max_dd_10y
	•	❌ 不在原始表里使用 current_price, current_pe 等。
	2.	所有「Current / Snapshot」类字段，只能出现在：
	•	metric_details 或等价的快照表；
	•	或后端传给前端的 DashboardData 对象中。
	3.	新增列/表时：
	•	必须写清楚 时间语义（是「当日值」还是「滚动窗口」）。
	•	保证 ETL 过程 幂等：多次运行不会重复插入同一日期数据。

⸻

7. 与用户交互时（编程 AI 行为规范）
	1.	当你为 VERA 写代码/重构时：
	•	先确认 使用的金融定义 是否与以上原则一致；
	•	如需更改定义（例如回撤算法），必须在注释中写明对旧数据的影响。
	2.	回答用户时：
	•	遇到「估值显得很奇怪」这类情况，优先检查：数据时点错配（新价格 + 旧 EPS）、稀疏 PE 点推导算法是否正确；
	•	解释清楚「绝对值 vs 历史分位」的区别，避免把单一 PE 误读成低估/高估。
	3.	永远不要：
	•	擅自引入新的状态命名（例如新建 D7、R4），而不通过 YAML/配置；
	•	随意改动财报字段的含义，只为了「方便」实现某个功能。

8. 代码注释规范
	1.	文件头注释约束：
	•	每一个代码文件的前部，必须包含一段注释；
	•	内容：描述本代码文件所要实现的主要功能和关键点；
	•	权限：这段注释的添加和修改，必须经过用户在前台批准单独才能进行（禁止 AI 擅自静默修改核心意图）。


9. 版本控制与文件安全规范（AI 必须遵守）

	1.	创建新文件后必须立即 commit（最高优先级）：
	•	每当 AI 创建了新的 .py、.yaml、.md、.sql 等源文件，必须在同一次对话中立即执行：
		git add <新文件路径>
		git commit -m "feat/fix/restore: <简短描述文件作用>"
	•	❌ 禁止：只写文件不 commit，让文件游离在 git 版本控制之外。
	•	背景教训：metrics/recent_cycle_engine.py 和 metrics/risk_metrics.py 因未 commit 而丢失，
	  只能靠逆向 .pyc 字节码才能恢复，风险极高。

	2.	对话结束前执行游离文件检查：
	•	每次对话的最后阶段，AI 应主动运行以下命令：
		git status --short | grep "^??"
	•	若输出包含 .py / .yaml / .md 等源文件，必须提示用户并询问是否 commit。

	3.	字节码缓存不能替代源文件：
	•	__pycache__/*.pyc 不纳入版本控制（已在 .gitignore 排除）。
	•	AI 创建的任何 .py 文件，必须确保对应 .py 源文件在 git 中有记录。

	4.	高风险操作必须二次确认：
	以下操作执行前，AI 必须明确告知用户风险并等待确认：
	•	删除任何 .py 源文件；
	•	执行 git reset --hard / git checkout -- . 等覆盖工作区的命令；
	•	批量清理 __pycache__ 目录。

⸻

总结一句给编程 AI：
在 VERA 里，所有数字都要能说清楚「怎么算的、对应什么经济含义、历史上处于哪个段位」，任何看不懂的魔法写法都是潜在 Bug，应当被消灭。
