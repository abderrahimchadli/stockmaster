#!/usr/bin/env python3
"""
Simple script to check Python syntax
"""

import py_compile
import sys

def check_file(filename):
    try:
        py_compile.compile(filename, doraise=True)
        print(f"✅ {filename} has valid syntax")
        return True
    except py_compile.PyCompileError as e:
        print(f"❌ {filename} has syntax errors:")
        print(e)
        return False
    except Exception as e:
        print(f"❌ Error checking {filename}:")
        print(e)
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python check_syntax.py <filename>")
        sys.exit(1)
    
    filename = sys.argv[1]
    result = check_file(filename)
    sys.exit(0 if result else 1) 