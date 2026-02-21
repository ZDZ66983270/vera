# 港股历史K线数据获取测试 - 使用说明

## 📌 脚本概述

本测试脚本 `test_futu_hk_kline.py` 用于通过 Futu OpenAPI 获取港股历史K线数据，**重点监控PE比率（市盈率）的返回情况**。

测试股票：
- **09988.HK** - 阿里巴巴-SW
- **00005.HK** - 汇丰控股

## 🔧 环境准备

### 1. 安装 Futu API Python 库

```bash
pip install futu-api
```

### 2. 下载并启动 FutuOpenD

FutuOpenD 是富途提供的行情网关程序，必须先启动才能使用API。

**下载地址：**
- 官方文档：https://openapi.futunn.com/futu-api-doc/
- 下载页面：https://www.futunn.com/download/OpenAPI

**启动方法：**
```bash
# Mac/Linux
./FutuOpenD

# Windows
FutuOpenD.exe
```

**默认配置：**
- 监听地址：`127.0.0.1`
- 端口：`11111`

### 3. 配置说明

如果您修改了 FutuOpenD 的监听端口，需要在脚本中相应修改：

```python
# 在 fetch_hk_stock_kline 函数中修改
quote_ctx = ft.OpenQuoteContext(host='127.0.0.1', port=11111)  # 修改端口号
```

## 🚀 运行脚本

```bash
cd /Users/zhangzy/My\ Docs/Privates/22-AI编程/VERA
python3 test_futu_hk_kline.py
```

## 📊 输出内容说明

### 1. 基本数据获取信息

```
==============================================================
正在获取 HK.09988 的历史K线数据...
时间范围: 2025-10-09 至 2026-01-08
==============================================================

✓ 成功获取 63 条K线数据

数据列: ['code', 'time_key', 'open', 'close', 'high', 'low', 
         'pe_ratio', 'turnover_rate', 'volume', 'turnover', 'change_rate', 'last_close']
```

### 2. PE比率统计信息

```
✓ PE比率字段存在

PE比率统计信息:
count     63.000000
mean      15.234567
std        2.345678
min       12.500000
25%       14.200000
50%       15.100000
75%       16.300000
max       18.900000

PE > 0 的数据条数: 63 / 63
PE = 0 的数据条数: 0
```

### 3. PE详细分析

```
==============================================================
09988 PE数据详细分析
==============================================================

1. PE值分布:
   PE = 0:     0 条 (0.0%)
   PE > 0:    63 条 (100.0%)
   PE < 0:     0 条 (0.0%)

2. 有效PE数据统计 (PE > 0):
   最小值: 12.50
   最大值: 18.90
   平均值: 15.23
   中位数: 15.10

3. 最近30天PE趋势:
time_key     close  pe_ratio
2025-12-09   95.50     15.20
2025-12-10   96.20     15.32
...
```

## 🔍 重点监控项

### PE比率字段检查

脚本会重点检查以下内容：

1. **PE字段是否存在**
   - ✓ 存在：正常显示统计信息
   - ✗ 不存在：显示警告信息和可用字段列表

2. **PE数据有效性**
   - PE > 0：有效的市盈率数据
   - PE = 0：可能是数据缺失或股票亏损
   - PE < 0：通常表示公司亏损（负市盈率）

3. **PE数据完整性**
   - 统计有效PE数据占比
   - 显示PE值的分布情况
   - 展示PE随时间的变化趋势

## ⚙️ 自定义参数

### 修改测试股票

```python
# 在 main() 函数中修改
stocks = ['09988', '00005', '00700']  # 添加腾讯控股
```

### 修改时间范围

```python
# 在 main() 函数中修改
end_date = datetime.now().strftime('%Y-%m-%d')
start_date = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d')  # 改为6个月
```

### 修改K线类型

```python
# 在 fetch_hk_stock_kline 函数调用时修改
data = fetch_hk_stock_kline(stock_code, start_date, end_date, ktype=ft.KLType.K_WEEK)  # 周K线
```

可用的K线类型：
- `ft.KLType.K_DAY` - 日K线（默认）
- `ft.KLType.K_WEEK` - 周K线
- `ft.KLType.K_MON` - 月K线
- `ft.KLType.K_1M` - 1分钟K线
- `ft.KLType.K_5M` - 5分钟K线
- `ft.KLType.K_15M` - 15分钟K线
- `ft.KLType.K_30M` - 30分钟K线
- `ft.KLType.K_60M` - 60分钟K线

## ⚠️ 常见问题

### 1. 连接失败

**错误信息：** `Connection refused` 或 `无法连接到服务器`

**解决方法：**
- 确认 FutuOpenD 已启动
- 检查端口号是否正确（默认11111）
- 检查防火墙设置

### 2. PE数据全为0

**可能原因：**
- 股票处于停牌状态
- 公司财报数据未更新
- 该时间段内公司亏损

**解决方法：**
- 更换测试股票
- 调整时间范围
- 查看其他字段是否正常返回

### 3. 数据量过少

**可能原因：**
- 时间范围内有节假日、周末
- 股票停牌
- 新上市股票历史数据不足

**解决方法：**
- 扩大时间范围
- 检查股票交易状态

## 📝 API参数说明

### request_history_kline 主要参数

| 参数 | 类型 | 说明 | 示例 |
|------|------|------|------|
| code | str | 股票代码 | 'HK.09988' |
| start | str | 开始日期 | '2025-01-01' |
| end | str | 结束日期 | '2025-12-31' |
| ktype | KLType | K线类型 | ft.KLType.K_DAY |
| autype | AuType | 复权类型 | ft.AuType.QFQ（前复权） |
| fields | list | 返回字段 | [ft.KLField.ALL] |
| max_count | int | 最大返回条数 | 1000 |

### 复权类型说明

- `ft.AuType.QFQ` - 前复权（推荐）
- `ft.AuType.HFQ` - 后复权
- `ft.AuType.NONE` - 不复权

## 📚 参考资料

- [Futu OpenAPI 官方文档](https://openapi.futunn.com/futu-api-doc/)
- [获取历史K线接口说明](https://openapi.futunn.com/futu-api-doc/quote/request-history-kline.html)
- [Python API 参考](https://openapi.futunn.com/futu-api-doc/api/Quote_API.html#request_history_kline)

## 💡 使用建议

1. **首次运行**：建议先用默认参数运行，确认环境配置正确
2. **PE监控**：重点关注 "PE > 0 的数据条数" 和 "有效PE数据统计"
3. **数据验证**：对比富途牛牛APP中的数据，验证准确性
4. **批量测试**：可添加更多港股代码进行批量测试
5. **定期运行**：建议定期运行以监控PE数据的稳定性

## 🎯 测试目标

本脚本的主要测试目标：

✅ 验证 Futu API 能否成功获取港股历史K线数据  
✅ 确认返回数据中包含 `pe_ratio` 字段  
✅ 检查PE数据的完整性和有效性  
✅ 分析PE数据的分布和趋势  
✅ 为后续集成到VERA系统提供参考  
