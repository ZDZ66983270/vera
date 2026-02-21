import sqlite3
import os

DB_PATH = "vera.db"

def migrate():
    if not os.path.exists(DB_PATH):
        print(f"Database {DB_PATH} not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("--- Starting Quality Schema Migration ---")

    # 1. Check if old table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='quality_snapshot'")
    if not cursor.fetchone():
        print("Table quality_snapshot does not exist. Creating fresh.")
    else:
        print("Backing up existing quality_snapshot...")
        cursor.execute("DROP TABLE IF EXISTS quality_snapshot_old")
        cursor.execute("ALTER TABLE quality_snapshot RENAME TO quality_snapshot_old")

    # 2. Create new table
    print("Creating new quality_snapshot table...")
    cursor.execute("""
        CREATE TABLE quality_snapshot (
            snapshot_id TEXT NOT NULL,
            asset_id    TEXT NOT NULL,

            -- Business Quality（业务韧性）
            revenue_stability_flag    TEXT,  -- STRONG | MID | WEAK
            cyclicality_flag          TEXT,  -- LOW | MID | HIGH
            moat_proxy_flag           TEXT,  -- STRONG | MID | WEAK

            -- Financial Quality（财务缓冲）
            balance_sheet_flag        TEXT,  -- STRONG | MID | WEAK
            cashflow_coverage_flag    TEXT,  -- STRONG | MID | WEAK
            leverage_risk_flag        TEXT,  -- LOW | MID | HIGH

            -- Governance / Policy（制度缓冲）
            payout_consistency_flag   TEXT,  -- POSITIVE | NEUTRAL | NEGATIVE
            dilution_risk_flag        TEXT,  -- LOW | HIGH
            regulatory_dependence_flag TEXT, -- LOW | MID | HIGH

            -- 汇总
            quality_buffer_level      TEXT,  -- STRONG | MODERATE | WEAK
            quality_summary           TEXT,  -- ≤ 2 行解释
            quality_notes             TEXT,  -- 详细备注 (JSON)

            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (snapshot_id, asset_id)
        )
    """)

    # 3. Migrate data if old table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='quality_snapshot_old'")
    if cursor.fetchone():
        print("Migrating data from quality_snapshot_old...")
        try:
            cursor.execute("""
                INSERT INTO quality_snapshot (
                    snapshot_id, asset_id, revenue_stability_flag, cyclicality_flag, 
                    moat_proxy_flag, balance_sheet_flag, cashflow_coverage_flag, 
                    leverage_risk_flag, payout_consistency_flag, dilution_risk_flag, 
                    regulatory_dependence_flag, quality_buffer_level, quality_summary, 
                    quality_notes, created_at
                )
                SELECT 
                    snapshot_id, asset_id, revenue_stability_flag, cyclicality_flag, 
                    moat_proxy_flag, balance_sheet_flag, cashflow_coverage_flag, 
                    leverage_risk_flag, payout_consistency_flag, dilution_risk_flag, 
                    regulatory_dependence_flag, quality_buffer_level, quality_summary, 
                    quality_notes, created_at
                FROM quality_snapshot_old
            """)
            print("Migration successful.")
        except Exception as e:
            print(f"Data migration partially failed or skipped: {e}")
            print("New table is empty, but structure is correct.")

    conn.commit()
    conn.close()
    print("--- Migration Finished ---")

if __name__ == "__main__":
    migrate()
