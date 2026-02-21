#!/usr/bin/env python3
"""
Quick test script to reproduce the analysis error for CN:STOCK:600036
"""

import sys
sys.path.insert(0, '/Users/zhangzy/My Docs/Privates/22-AI编程/VERA')

from engine.snapshot_builder import run_snapshot
from datetime import datetime

try:
    print("Testing run_snapshot for CN:STOCK:600036...")
    result = run_snapshot("CN:STOCK:600036", as_of_date=datetime(2026, 1, 28))
    print(f"Success! Result type: {type(result)}")
    if result:
        print(f"Result attributes: {dir(result)}")
except Exception as e:
    print(f"Error occurred: {e}")
    import traceback
    traceback.print_exc()
