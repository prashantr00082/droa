import os
import sys
import json
import shutil

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
from deep_rkb_agent.agents.reciprocity import run_reciprocity_check

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "fixtures/sample_repo"))

def test_reciprocity():
    # Setup mock JSON sidecars
    docs_dir = os.path.join(REPO, "docs")
    modules_dir = os.path.join(docs_dir, "modules")
    arch_dir = os.path.join(docs_dir, "architecture")
    
    os.makedirs(modules_dir, exist_ok=True)
    os.makedirs(arch_dir, exist_ok=True)
    
    # Module A claims to depend on Module B, but Module B does not say it is used by Module A
    # Module B claims to be used by Module C, and Module C acknowledges depending on Module B
    mock_a = {
        "source": "module_A.py",
        "symbols": [
            {"name": "func_a", "depends_on": ["module_B.py"], "used_by": []}
        ]
    }
    mock_b = {
        "source": "module_B.py",
        "symbols": [
            {"name": "func_b", "depends_on": [], "used_by": ["module_C.py"]}
        ]
    }
    mock_c = {
        "source": "module_C.py",
        "symbols": [
            {"name": "func_c", "depends_on": ["module_B.py"], "used_by": []}
        ]
    }
    
    for mock_data in [mock_a, mock_b, mock_c]:
        with open(os.path.join(modules_dir, f"{mock_data['source']}.json"), "w") as f:
            json.dump(mock_data, f)
            
    # Run reciprocity checker
    report_path = run_reciprocity_check(REPO)
    
    # Validate report
    assert os.path.exists(report_path)
    with open(report_path, "r") as f:
        report_content = f.read()
        
    print("Reciprocity Report Output:")
    print(report_content)
    
    # Should flag module_A -> module_B mismatch
    assert "module_A.py` claims to depend on `module_B.py`, but `module_B.py` does not list `module_A.py` in its `used_by`" in report_content
    
    # Should NOT flag module_C -> module_B because they acknowledge each other
    assert "module_C.py` claims to depend on `module_B.py`" not in report_content
    
    # Clean up mock files
    shutil.rmtree(docs_dir)
    print("  PASS: reciprocity checker correctly found mismatches and ignored valid claims\n")

if __name__ == "__main__":
    test_reciprocity()
    print("All Synthesizer tests passed!")
