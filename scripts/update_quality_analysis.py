import sqlite3
import uuid
import datetime
from analysis.quality_assessment import build_quality_flags
from db.quality_snapshot import save_quality_snapshot

DB_PATH = "data/stock_analyzer.db"

def get_connection():
    return sqlite3.connect(DB_PATH)

def fetch_fundamentals(asset_id: str, conn):
    """
    Combine data from financial_history (TTM) and fundamentals_annual (History)
    and assets (Sector/Industry)
    """
    cursor = conn.cursor()
    
    # 1. Fetch TTM data (financial_history) - Get latest
    # Note: table PK is (asset_id, report_date). We want the most recent one.
    cursor.execute("""
        SELECT * FROM financial_history 
        WHERE asset_id = ? 
        ORDER BY report_date DESC LIMIT 1
    """, (asset_id,))
    ttm_row = cursor.fetchone()
    
    # Get column names
    ttm_cols = [description[0] for description in cursor.description] if ttm_row else []
    ttm_data = dict(zip(ttm_cols, ttm_row)) if ttm_row else {}
    
    # 2. Fetch History (fundamentals_annual) - Get all years sorted
    cursor.execute("""
        SELECT * FROM fundamentals_annual 
        WHERE asset_id = ? 
        ORDER BY fiscal_year ASC
    """, (asset_id,))
    hist_rows = cursor.fetchall()
    hist_cols = [description[0] for description in cursor.description] if hist_rows else []
    
    revenue_history = []
    
    for r in hist_rows:
        row_dict = dict(zip(hist_cols, r))
        # Collect revenue history for stability calc
        revenue_history.append(row_dict.get('revenue'))
        
    # 3. Fetch Sector Info (assets)
    cursor.execute("SELECT sector FROM assets WHERE asset_id = ?", (asset_id,))
    res = cursor.fetchone()
    sector = res[0] if res else None
    
    # Combine into a single dict for analysis
    # Map DB columns to analysis keys if needed (analysis often uses same keys or aliases)
    combined = ttm_data.copy()
    combined['revenue_history'] = revenue_history
    combined['sector'] = sector
    
    # Ensure specific keys expected by assessment are present (DB cols match mostly)
    # Mapping check:
    # DB: revenue_ttm -> Analysis: revenue_ttm (Matches)
    # DB: net_income_ttm -> Analysis: net_income_ttm (Matches)
    # DB: operating_cashflow_ttm -> Analysis: operating_cashflow_ttm (Matches)
    # ...
    
    return combined

def main():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get list of assets to process
    # Just process those that exist in financial_history (active subset)
    cursor.execute("SELECT DISTINCT asset_id FROM financial_history")
    assets = [r[0] for r in cursor.fetchall()]
    
    print(f"Found {len(assets)} assets to analyze.")
    
    for asset_id in assets:
        print(f"Analyzing {asset_id}...")
        try:
            fund_data = fetch_fundamentals(asset_id, conn)
            if not fund_data:
                print(f"  Skipping {asset_id}: No fundamental data found.")
                continue
                
            # Run analysis
            result = build_quality_flags(fund_data)
            
            # Prepare snapshot ID (Mock or link to latest analysis snapshot if exists)
            # For MVP, we generate a new UUID for the quality record linking.
            # Ideally this should link to the latest main AnalysisSnapshot.
            # But quality_snapshot table treats snapshot_id as a key which usually refers to AnalysisSnapshot.
            # If AnalysisSnapshot doesn't exist for today, we might have an issue linking FK if enforced.
            # Let's check schema: FOREIGN KEY (snapshot_id) REFERENCES analysis_snapshot(snapshot_id)
            # So we MUST have a valid snapshot_id.
            
            # Fetch latest snapshot_id for asset
            cursor.execute("""
                SELECT snapshot_id FROM analysis_snapshot 
                WHERE asset_id = ? 
                ORDER BY as_of_date DESC LIMIT 1
            """, (asset_id,))
            snap_res = cursor.fetchone()
            
            if not snap_res:
                # If no snapshot exists (maybe user never ran 'analyze' in dashboard), we can't save quality.
                # Or we insert a dummy snapshot.
                # Let's see if we can create one or just skip.
                # For imports/MVP, user usually refreshes dashboard which triggers snapshot.
                # BUT here we are running standalone.
                # OPTION: Create a placeholder snapshot if needed.
                # For now, let's try to reuse latest. If None, warn.
                print(f"  Warning: No Analysis Snapshot found for {asset_id}. Creating temporary one.")
                
                # Create dummy snapshot for today
                snap_id = str(uuid.uuid4())
                today = datetime.date.today().isoformat()
                cursor.execute("""
                    INSERT INTO analysis_snapshot (snapshot_id, asset_id, as_of_date, risk_level, valuation_status)
                    VALUES (?, ?, ?, 'UNKNOWN', 'UNKNOWN')
                """, (snap_id, asset_id, today))
                conn.commit() # Commit snapshot first
                
            else:
                snap_id = snap_res[0]

            # Save
            save_quality_snapshot(
                snapshot_id=snap_id,
                asset_id=asset_id,
                revenue_stability_flag=result["revenue_stability_flag"],
                cyclicality_flag=result["cyclicality_flag"],
                moat_proxy_flag=result["moat_proxy_flag"],
                balance_sheet_flag=result["balance_sheet_flag"],
                cashflow_coverage_flag=result["cashflow_coverage_flag"],
                leverage_risk_flag=result["leverage_risk_flag"],
                payout_consistency_flag=result["payout_consistency_flag"],
                dilution_risk_flag=result["dilution_risk_flag"],
                regulatory_dependence_flag=result["regulatory_dependence_flag"],
                quality_buffer_level=result["quality_buffer_level"],
                quality_summary=result["quality_summary"],
                notes={"details": result["quality_notes"]}
            )
            print(f"  Saved quality buffer: {result['quality_buffer_level']}")
            
        except Exception as e:
            print(f"  Error analyzing {asset_id}: {e}")
            import traceback
            traceback.print_exc()

    conn.close()
    print("Done.")

if __name__ == "__main__":
    main()
