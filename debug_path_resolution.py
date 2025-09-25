#!/usr/bin/env python3
"""
Debug script to test path resolution in different environments
"""
import os
import sys
from pathlib import Path
from resource_utils import get_resource_path, load_env_file

print("=== DEBUG PATH RESOLUTION ===")
print(f"sys.frozen: {getattr(sys, 'frozen', False)}")
print(f"sys._MEIPASS: {hasattr(sys, '_MEIPASS')}")
print(f"sys.executable: {sys.executable}")
print(f"__file__: {__file__ if '__file__' in globals() else 'Not available'}")
print(f"Current working directory: {os.getcwd()}")

# Test our resource path function
print("\n=== RESOURCE PATH CALCULATION ===")
resource_path = get_resource_path()
env_path = get_resource_path(".env")
print(f"Base resource path: {resource_path}")
print(f"Env file path: {env_path}")
print(f"Env file exists: {env_path.exists()}")

if env_path.exists():
    print(f"Env file size: {env_path.stat().st_size} bytes")
else:
    print("Env file does not exist at calculated path")

# Test loading
print("\n=== LOADING TEST ===")
result = load_env_file()
print(f"Load result: {result}")

# Show environment variables
print("\n=== AZURE OPENAI CONFIG ===")
print(f"AZURE_OPENAI_API_KEY: {'SET' if os.getenv('AZURE_OPENAI_API_KEY') else 'NOT SET'}")
print(f"AZURE_OPENAI_ENDPOINT: {os.getenv('AZURE_OPENAI_ENDPOINT', 'NOT SET')}")