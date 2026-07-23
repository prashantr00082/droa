import sys
import os

sys.path.insert(0, os.path.abspath("src"))
from deep_rkb_agent.tools.ast_parser import extract_symbols

java_file = "tests/fixtures/sample_repo/Main.java"
go_file = "tests/fixtures/sample_repo/main.go"
py_file = "tests/fixtures/sample_repo/main.py"

print("--- JAVA ---")
print(extract_symbols(java_file))

print("\n--- GO ---")
print(extract_symbols(go_file))

print("\n--- PYTHON ---")
print(extract_symbols(py_file))
