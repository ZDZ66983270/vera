-- 数据来源追踪字段迁移脚本
-- 为 financial_history 表添加数据来源追踪功能

-- 1. 添加数据来源字段
ALTER TABLE financial_history ADD COLUMN data_source TEXT DEFAULT 'UNKNOWN';

-- 2. 添加导入时间戳
ALTER TABLE financial_history ADD COLUMN import_timestamp TEXT;

-- 3. 添加导入者（预留，可用于多用户场景）
ALTER TABLE financial_history ADD COLUMN imported_by TEXT;

-- 4. 添加源文件名
ALTER TABLE financial_history ADD COLUMN source_file_name TEXT;

-- 5. 添加置信度分数（OCR等自动识别的准确度）
ALTER TABLE financial_history ADD COLUMN source_confidence REAL DEFAULT 1.0;

-- 注意：SQLite 的 ALTER TABLE 只支持 ADD COLUMN
-- 如果需要修改现有字段，需要重建表
