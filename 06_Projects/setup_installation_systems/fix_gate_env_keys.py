#!/usr/bin/env python3
"""
Fix all Gate.io scripts to use environment variables only (no hardcoded defaults)
This fixes the INVALID_SIGNATURE error
"""

import os
import re
from pathlib import Path

FILES_TO_FIX = [
    "beast.py",
    "enhanced_gate_bot.py", 
    "gate.spread.py",
    "gatefutures.py",
    "gateio_llm_trader.py",
    "gatenew.py",
    "gatenewclaude_fixed.py",
    "gatesomething.py",
    "local_ollama_trader.py",
    "microgategodborbit.py",
    "simple_gateio_bot.py",
]

def fix_file(filepath):
    """Fix a single file to use env vars only"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original = content
        
        # Replace getenv with default values - change to getenv without defaults for private APIs
        content = re.sub(
            r'GATE_API_KEY\s*=\s*os\.getenv\("GATE_API_KEY"[^)]*\)',
            'GATE_API_KEY = os.getenv("GATE_API_KEY", "")',
            content
        )
        content = re.sub(
            r'GATE_API_SECRET\s*=\s*os\.getenv\("GATE_API_SECRET"[^)]*\)',
            'GATE_API_SECRET = os.getenv("GATE_API_SECRET", "")',
            content
        )
        
        if content != original:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✅ Fixed: {filepath.name}")
            return True
        return False
        
    except Exception as e:
        print(f"❌ Error: {filepath.name} - {e}")
        return False

print("🔧 Fixing Gate.io scripts to use environment variables...\n")
downloads = Path("/Users/alep/Downloads")
fixed = 0

for fname in FILES_TO_FIX:
    fpath = downloads / fname
    if fpath.exists():
        if fix_file(fpath):
            fixed += 1
    else:
        print(f"⚠️  Not found: {fname}")

print(f"\n✅ Fixed {fixed} files")
print("\n⚠️  IMPORTANT: Export your API keys before running scripts:")
print("   source /Users/alep/Downloads/export_gate_keys.sh")
