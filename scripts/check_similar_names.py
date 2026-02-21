import sqlite3
import sys
import os
from difflib import SequenceMatcher

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from db.connection import get_connection

def combined_similarity(a, b):
    return SequenceMatcher(None, a, b).ratio()

def check_names():
    conn = get_connection()
    cursor = conn.cursor()
    
    print("Fetching all assets...")
    cursor.execute("SELECT asset_id, name, market FROM assets WHERE name IS NOT NULL AND name != ''")
    rows = cursor.fetchall()
    conn.close()
    
    assets = [{"id": r[0], "name": r[10] if len(r)>10 else r[1], "market": r[2]} for r in rows] # r[1] is name
    
    # 1. Exact Duplicates (Case Insensitive)
    print("\n--- 1. Exact Name Duplicates (Case Insensitive) ---")
    name_map = {}
    for a in assets:
        n_lower = a["name"].strip().lower()
        if n_lower not in name_map:
            name_map[n_lower] = []
        name_map[n_lower].append(a)
    
    found_exact = False
    for name, group in name_map.items():
        if len(group) > 1:
            found_exact = True
            print(f"Name: '{group[0]['name']}'")
            for item in group:
                print(f"  - {item['id']} ({item['market']})")
    
    if not found_exact:
        print("No exact duplicates found.")

    # 2. Similar Names (Simple Fuzzy Check)
    # Checking O(N^2) is expensive if N is large.
    # We can optimize by grouping by market or first letter, likely duplicates assume same market/language.
    # For now, let's limit comparison to O(N^2) but only report high similarity > 0.8
    
    print("\n--- 2. Similar Names (Similarity > 0.85) ---")
    # Sort by name to make close names adjacent? 
    # Actually just comparing sorted list is decent for prefix matches, but not "Alibaba" vs "Alibaba Group"
    
    # Let's filter to only compare assets within same market or 'US'/'HK'/'CN' sets to reduce noise?
    # Actually user wants to find issues. Let's run full check but limit output count.
    
    assets_sorted = sorted(assets, key=lambda x: x["name"])
    found_similar = 0
    
    seen_pairs = set()
    
    for i in range(len(assets_sorted)):
        for j in range(i + 1, len(assets_sorted)):
            a = assets_sorted[i]
            b = assets_sorted[j]
            
            # Optimization: If sorted names start diverging too much, break?
            # No, because "Tenc" and "Tenc" are close, but "Alibaba" and "BABA" are not.
            # But we are checking name similarity.
            
            # Quick check: substring
            name_a = a["name"]
            name_b = b["name"]
            
            if name_a == name_b: continue # Handled by exact check
            
            sim = combined_similarity(name_a.lower(), name_b.lower())
            
            if sim > 0.85:
                # Filter out obvious ones like suffix difference if ID is different?
                # Just report it.
                pair_key = tuple(sorted([a["id"], b["id"]]))
                if pair_key in seen_pairs: continue
                seen_pairs.add(pair_key)
                
                print(f"Similarity {sim:.2f}:")
                print(f"  A: {a['name']} ({a['id']})")
                print(f"  B: {b['name']} ({b['id']})")
                found_similar += 1
                if found_similar > 50:
                    print("... (Capping output at 50 pairs) ...")
                    return

    if found_similar == 0:
        print("No highly similar names found.")

if __name__ == "__main__":
    check_names()
