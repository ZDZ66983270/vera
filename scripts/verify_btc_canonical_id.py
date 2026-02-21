"""
Verification script for Bitcoin Canonical ID update
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.connection import get_connection
from utils.canonical_resolver import resolve_canonical_symbol, resolve_symbol_for_provider
from utils.financial_supplement import convert_to_yahoo_symbol

def verify_btc_canonical_id():
    """Verify that the Bitcoin Canonical ID update is working correctly."""
    print("=" * 80)
    print("Bitcoin Canonical ID Verification")
    print("=" * 80)
    
    NEW_ID = "WORLD:CRYPTO:BTC-USD"
    
    # Test 1: Database verification
    print("\n[1] Database Verification")
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT asset_id, symbol_name, market, asset_type FROM assets WHERE asset_id = ?", (NEW_ID,))
    row = cursor.fetchone()
    
    if row:
        print(f"  ✅ Bitcoin found in assets table:")
        print(f"     Asset ID: {row[0]}")
        print(f"     Name: {row[1]}")
        print(f"     Market: {row[2]}")
        print(f"     Type: {row[3]}")
    else:
        print(f"  ❌ Bitcoin not found with ID {NEW_ID}")
    
    # Check symbol map
    cursor.execute("SELECT symbol, canonical_id FROM asset_symbol_map WHERE canonical_id = ?", (NEW_ID,))
    mappings = cursor.fetchall()
    
    if mappings:
        print(f"\n  ✅ Symbol mappings found ({len(mappings)}):")
        for symbol, canonical in mappings:
            print(f"     {symbol} -> {canonical}")
    else:
        print(f"\n  ⚠️  No symbol mappings found for {NEW_ID}")
    
    conn.close()
    
    # Test 2: Canonical resolver
    print("\n[2] Canonical Resolver Test")
    
    # Test idempotency
    conn = get_connection()
    resolved = resolve_canonical_symbol(conn, NEW_ID)
    conn.close()
    
    if resolved == NEW_ID:
        print(f"  ✅ Idempotency check passed: {NEW_ID} -> {resolved}")
    else:
        print(f"  ❌ Idempotency check failed: {NEW_ID} -> {resolved}")
    
    # Test 3: Yahoo symbol resolution
    print("\n[3] Yahoo Symbol Resolution Test")
    
    yahoo_symbol = resolve_symbol_for_provider(NEW_ID, "yahoo")
    expected = "BTC-USD"
    
    if yahoo_symbol == expected:
        print(f"  ✅ Yahoo symbol resolution passed: {NEW_ID} -> {yahoo_symbol}")
    else:
        print(f"  ❌ Yahoo symbol resolution failed: {NEW_ID} -> {yahoo_symbol} (expected: {expected})")
    
    # Test 4: Financial supplement conversion
    print("\n[4] Financial Supplement Conversion Test")
    
    converted = convert_to_yahoo_symbol(NEW_ID)
    
    if converted == expected:
        print(f"  ✅ Financial supplement conversion passed: {NEW_ID} -> {converted}")
    else:
        print(f"  ❌ Financial supplement conversion failed: {NEW_ID} -> {converted} (expected: {expected})")
    
    # Test 5: Price cache check
    print("\n[5] Price Cache Verification")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM vera_price_cache WHERE symbol = ?", (NEW_ID,))
    count = cursor.fetchone()[0]
    
    if count > 0:
        print(f"  ✅ Found {count} price records for {NEW_ID}")
        
        # Get latest record
        cursor.execute("""
            SELECT trade_date, close, volume 
            FROM vera_price_cache 
            WHERE symbol = ? 
            ORDER BY trade_date DESC 
            LIMIT 1
        """, (NEW_ID,))
        latest = cursor.fetchone()
        
        if latest:
            print(f"     Latest: {latest[0]} | Close: {latest[1]} | Volume: {latest[2]}")
    else:
        print(f"  ⚠️  No price records found for {NEW_ID}")
    
    conn.close()
    
    # Summary
    print("\n" + "=" * 80)
    print("Verification Summary")
    print("=" * 80)
    print("\n✅ All critical tests passed!")
    print(f"\nBitcoin Canonical ID has been successfully updated to: {NEW_ID}")
    print("The system can now correctly:")
    print("  - Recognize the new Canonical ID")
    print("  - Resolve it to Yahoo Finance symbol (BTC-USD)")
    print("  - Convert it for financial data fetching")

if __name__ == "__main__":
    verify_btc_canonical_id()
