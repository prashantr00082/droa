import os
import sys

# Ensure src is in PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from deep_rkb_agent.agents.validator import validate_module
from deep_rkb_agent.schemas import ModuleSidecar, SymbolDoc

def run_tests():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "fixtures/sample_repo"))
    file_path = "utils.py"
    
    # Mock Sidecar (Missing 'helper' function to lower API coverage score)
    sidecar = ModuleSidecar(
        module="utils",
        source="utils.py",
        confidence=0.9,
        symbols=[],  # Empty list to fail API coverage (AST has 1 function 'helper')
        external_deps=[],
        extension_points=[],
        config_keys=[],
        markdown_doc="mock"
    )
    
    # Mock Markdown with missing headers and bad citations
    markdown_doc_bad = """
    ## Purpose
    This is a test [utils.py:1] (valid)
    This is bad [utils.py:999] (invalid line)
    This is worse [doesnotexist.py:1] (invalid file)
    """
    
    # Validate Bad Doc
    # Template: 1/5 = 0.2
    # Citations: 1/3 = 0.333
    # API: 0/1 = 0.0
    # Confidence = (0.2 * 0.2) + (0.5 * 0.333) + (0.3 * 0.0) = 0.04 + 0.166 = 0.206
    confidence_bad = validate_module(repo_root, file_path, markdown_doc_bad, sidecar)
    print(f"Bad Doc Confidence: {confidence_bad}")
    assert confidence_bad < 0.25, f"Expected < 0.25, got {confidence_bad}"
    
    # Mock Good Doc
    sidecar_good = sidecar.model_copy(update={
        "symbols": [
            SymbolDoc(
                name="helper",
                type="function",
                responsibility="help",
                collaborators=[],
                depends_on=[],
                used_by=[],
                source_ref="utils.py:1"
            )
        ]
    })
    
    markdown_doc_good = """
    ## Purpose
    Valid claim [utils.py:1].
    
    ## Responsibilities
    Valid claim 2 [utils.py:2].
    
    ## Public API
    ## Dependencies
    ## Things To Know Before Editing
    """
    
    # Template: 5/5 = 1.0
    # Citations: 2/2 = 1.0
    # API: 1/1 = 1.0
    # Confidence = 0.2*1.0 + 0.5*1.0 + 0.3*1.0 = 1.0
    confidence_good = validate_module(repo_root, file_path, markdown_doc_good, sidecar_good)
    print(f"Good Doc Confidence: {confidence_good}")
    assert confidence_good > 0.95, f"Expected > 0.95, got {confidence_good}"
    
    print("Validator tests passed successfully!")

if __name__ == "__main__":
    run_tests()
