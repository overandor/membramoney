#!/usr/bin/env python3
"""
Fix all hardcoded API keys to use environment variables
"""

import os
import re
import glob

def fix_file_env_keys(filepath):
    """Fix hardcoded keys in a file to use environment variables"""
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        original = content
        
        # Fix hardcoded API keys
        content = re.sub(
            r'GATE_API_KEY\s*=\s*"[^"]*"',
            'GATE_API_KEY = os.getenv("GATE_API_KEY", "")',
            content
        )
        
        content = re.sub(
            r'GATE_API_SECRET\s*=\s*"[^"]*"',
            'GATE_API_SECRET = os.getenv("GATE_API_SECRET", "")',
            content
        )
        
        # Fix hardcoded OpenRouter keys
        content = re.sub(
            r'OPENROUTER_API_KEY\s*=\s*"[^"]*"',
            'OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")',
            content
        )
        
        # Ensure os import exists
        if 'import os' not in content and 'from os import' not in content:
            if content.startswith('#!'):
                lines = content.split('\n')
                lines.insert(1, 'import os')
                content = '\n'.join(lines)
            else:
                content = 'import os\n' + content
        
        # Write back if changed
        if content != original:
            with open(filepath, 'w') as f:
                f.write(content)
            print(f"✅ Fixed: {filepath}")
            return True
        else:
            print(f"⏭️  Already fixed: {filepath}")
            return False
            
    except Exception as e:
        print(f"❌ Error fixing {filepath}: {e}")
        return False

def main():
    print("🔧 Fixing all hardcoded API keys to environment variables...")
    
    # Find all Python files
    py_files = glob.glob("*.py")
    
    fixed_count = 0
    total_count = 0
    
    for filepath in py_files:
        total_count += 1
        if fix_file_env_keys(filepath):
            fixed_count += 1
    
    print(f"\n📊 Summary:")
    print(f"   Total files: {total_count}")
    print(f"   Files fixed: {fixed_count}")
    print(f"   Already OK: {total_count - fixed_count}")
    
    print(f"\n🚀 All files now use environment variables!")
    print(f"\n💡 Export your keys with:")
    print(f"   export GATE_API_KEY='your-key'")
    print(f"   export GATE_API_SECRET='your-secret'")
    print(f"   export OPENROUTER_API_KEY='your-key'")

if __name__ == "__main__":
    main()
