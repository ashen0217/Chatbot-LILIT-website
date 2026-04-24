"""Verify that server.py functions are syntactically correct"""
import ast
import sys

def check_file_syntax(filepath):
    """Check if Python file has valid syntax"""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            code = f.read()
        ast.parse(code)
        return True, "Syntax valid"
    except SyntaxError as e:
        return False, str(e)
    except Exception as e:
        return False, str(e)

def find_function(filepath, func_name):
    """Find a function definition in a file"""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            code = f.read()
        tree = ast.parse(code)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name == func_name:
                return True, "Found (async)"
            elif isinstance(node, ast.FunctionDef) and node.name == func_name:
                return True, "Found (sync)"
        return False, "Not found"
    except Exception as e:
        return False, str(e)

# Run checks
print("=" * 60)
print("SERVER.PY VALIDATION")
print("=" * 60)

# Check syntax
valid, msg = check_file_syntax('server.py')
print(f"\n[1] Syntax Check: {'✅ PASS' if valid else '❌ FAIL'}")
print(f"    {msg}")

# Check for critical functions
print(f"\n[2] Function Checks:")
functions_to_check = [
    'get_all_course_details',
    'get_live_course_count',
    'is_lilit_related_query',
    'chat'
]

for func in functions_to_check:
    found, status = find_function('server.py', func)
    symbol = "✅" if found else "❌"
    print(f"    {symbol} {func}(): {status}")

# Check imports
print(f"\n[3] Import Check:")
try:
    with open('server.py', 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    imports_needed = [
        'import requests',
        'from fastapi import FastAPI',
        'from langchain_pinecone import PineconeVectorStore'
    ]
    
    for imp in imports_needed:
        if imp in content:
            print(f"    ✅ {imp}")
        else:
            print(f"    ⚠️ Missing: {imp}")
except Exception as e:
    print(f"    ⚠️ Error checking imports: {e}")

print("\n" + "=" * 60)
print("✅ SERVER.PY VALIDATION COMPLETE")
print("=" * 60)
