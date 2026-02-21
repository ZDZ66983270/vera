-- HK 市场字母代码修复 SQL 迁移脚本
-- 执行日期: 2026-01-05
-- 目的: 修正被错误补零的 HK 指数代码

BEGIN TRANSACTION;

-- 1. 修正 HSI (00HSI -> HSI)
UPDATE assets 
SET asset_id = 'HK:INDEX:HSI' 
WHERE asset_id = 'HK:INDEX:00HSI';

UPDATE asset_symbol_map 
SET canonical_id = 'HK:INDEX:HSI' 
WHERE canonical_id = 'HK:INDEX:00HSI';

UPDATE asset_universe 
SET asset_id = 'HK:INDEX:HSI' 
WHERE asset_id = 'HK:INDEX:00HSI';

UPDATE asset_universe 
SET market_index_id = 'HK:INDEX:HSI' 
WHERE market_index_id = 'HK:INDEX:00HSI';

-- 2. 修正 HSCE (0HSCE -> HSCE)
UPDATE assets 
SET asset_id = 'HK:INDEX:HSCE' 
WHERE asset_id = 'HK:INDEX:0HSCE';

UPDATE asset_symbol_map 
SET canonical_id = 'HK:INDEX:HSCE' 
WHERE canonical_id = 'HK:INDEX:0HSCE';

UPDATE asset_universe 
SET asset_id = 'HK:INDEX:HSCE' 
WHERE asset_id = 'HK:INDEX:0HSCE';

UPDATE asset_universe 
SET market_index_id = 'HK:INDEX:HSCE' 
WHERE market_index_id = 'HK:INDEX:0HSCE';

UPDATE vera_price_cache 
SET symbol = 'HK:INDEX:HSCE' 
WHERE symbol = 'HK:INDEX:0HSCE';

-- 3. 修正 HSCC (0HSCC -> HSCC)
UPDATE assets 
SET asset_id = 'HK:INDEX:HSCC' 
WHERE asset_id = 'HK:INDEX:0HSCC';

UPDATE asset_symbol_map 
SET canonical_id = 'HK:INDEX:HSCC' 
WHERE canonical_id = 'HK:INDEX:0HSCC';

UPDATE asset_universe 
SET asset_id = 'HK:INDEX:HSCC' 
WHERE asset_id = 'HK:INDEX:0HSCC';

UPDATE asset_universe 
SET market_index_id = 'HK:INDEX:HSCC' 
WHERE market_index_id = 'HK:INDEX:0HSCC';

UPDATE vera_price_cache 
SET symbol = 'HK:INDEX:HSCC' 
WHERE symbol = 'HK:INDEX:0HSCC';

COMMIT;

-- 验证结果
SELECT '=== 验证 assets 表 ===' as step;
SELECT asset_id, symbol_name FROM assets WHERE market='HK' AND asset_type='INDEX' ORDER BY asset_id;

SELECT '=== 验证 vera_price_cache 表 ===' as step;
SELECT symbol, COUNT(*) as records FROM vera_price_cache WHERE symbol LIKE 'HK:INDEX:%' GROUP BY symbol ORDER BY symbol;
