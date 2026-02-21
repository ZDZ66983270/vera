
import argparse
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.pdf_engine import PDFFinancialParser
from db.connection import get_connection

def ingest_report(pdf_path: str, asset_id: str):
    print(f"--- Ingesting PDF Report: {pdf_path} for {asset_id} ---")
    
    if not os.path.exists(pdf_path):
        print(f"Error: File not found {pdf_path}")
        return

    # 1. Parse PDF
    parser = PDFFinancialParser(pdf_path)
    try:
        print("Extracting text content...")
        parser.extract_content(max_pages=30) # Scan first 30 pages
        
        print("Parsing metrics...")
        metrics = parser.parse_financials()
        
        print("\n[Extracted Data]")
        for k, v in metrics.items():
            print(f"  {k}: {v}")
            
        if not metrics.get('report_date'):
            print("Warning: Could not determine Report Date from PDF. Using today's year end?")
            # Fallback logic or prompt? For now, if missing, abort save or require manual override
            # For automation, maybe extract from filename?
            pass
            
    except Exception as e:
        print(f"Parsing failed: {e}")
        return

    # 2. Save to Database
    if metrics.get('report_date'):
        save_to_db(asset_id, metrics)
    else:
        print("\n❌ Skipped saving: Report Date missing.")

def save_to_db(asset_id, metrics):
    conn = get_connection()
    cursor = conn.cursor()
    
    report_date = metrics['report_date']
    
    # Check if this record exists
    # We map 'net_profit' -> 'net_profit_ttm' (approx) or create new columns?
    # Existing schema: eps_ttm, net_profit_ttm, dividend_amount
    
    # Note: Annual report data is technically "Annual", not "TTM". 
    # But for end-of-year, Annual = TTM.
    # We should distinguish. For MVP, we overwrite TTM columns or just log it.
    
    # Simplest MVP: Write to financial_history (which has annual fields implicitly?)
    # financial_history columns: asset_id, report_date, eps_ttm, net_profit_ttm, dividend_amount...
    
    # We will assume extracted data is "Annual" and save it.
    
    print(f"\nSaving to DB for {asset_id} @ {report_date}...")
    
    try:
        cursor.execute("""
            INSERT INTO financial_history (
                asset_id, report_date, 
                eps_ttm, net_profit_ttm, dividend_amount,
                revenue_ttm  -- Assuming column exists or we map to it
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(asset_id, report_date) DO UPDATE SET
                eps_ttm = COALESCE(excluded.eps_ttm, financial_history.eps_ttm),
                net_profit_ttm = COALESCE(excluded.net_profit_ttm, financial_history.net_profit_ttm),
                dividend_amount = COALESCE(excluded.dividend_amount, financial_history.dividend_amount),
                revenue_ttm = COALESCE(excluded.revenue_ttm, financial_history.revenue_ttm)
        """, (
            asset_id, 
            report_date,
            metrics.get('eps'),
            metrics.get('net_profit'),
            metrics.get('dividend'),
            metrics.get('revenue')
        ))
        conn.commit()
        print("✅ Data saved successfully.")
        
    except Exception as e:
        print(f"Database Error: {e}")
        # If column revenue_ttm missing, we might fail. 
        # Check schema? Assuming standard schema.
        
    finally:
        conn.close()

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 ingest_pdf_report.py <pdf_path> <asset_id>")
    else:
        ingest_report(sys.argv[1], sys.argv[2])
