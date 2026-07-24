import re
import os
from typing import Dict, Any, List
from deep_rkb_agent.schemas import ModuleSidecar
from deep_rkb_agent.tools.ast_parser import extract_symbols

REQUIRED_HEADERS = [
    "## Purpose",
    "## Responsibilities",
    "## Public API",
    "## Dependencies",
    "## Things To Know Before Editing"
]

def validate_module(repo_root: str, file_path: str, markdown_doc: str, sidecar: ModuleSidecar) -> float:
    """
    Deterministically validates the generated module documentation and returns a confidence score.
    """
    abs_path = os.path.join(repo_root, file_path)
    
    # 1. Template Completeness Check (Weight: 0.2)
    headers_found = 0
    for header in REQUIRED_HEADERS:
        if header in markdown_doc:
            headers_found += 1
    template_score = headers_found / len(REQUIRED_HEADERS)
    
    # 2. Citation Check (Weight: 0.5)
    # Match pattern like [src/main.py:42]
    citation_pattern = r'\[([^\]]+):(\d+)\]'
    citations = re.findall(citation_pattern, markdown_doc)
    
    valid_citations = 0
    total_citations = len(citations)
    
    if total_citations > 0:
        for cited_file, line_str in citations:
            line_num = int(line_str)
            
            # Resolve basename citations to the current module being documented
            if cited_file == os.path.basename(file_path):
                cited_file = file_path
                
            cited_abs_path = os.path.join(repo_root, cited_file)
            if os.path.exists(cited_abs_path):
                try:
                    with open(cited_abs_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        if 1 <= line_num <= len(lines):
                            valid_citations += 1
                except Exception:
                    pass
        citation_score = valid_citations / total_citations
    else:
        # If no citations were made, that's a failure of the cite-or-drop rule
        citation_score = 0.0
        
    # 3. API Coverage Check (Weight: 0.3)
    ast_data = extract_symbols(abs_path)
    if "error" not in ast_data:
        ast_symbols = set(ast_data.get("classes", []) + ast_data.get("functions", []))
        doc_symbols = set(s.name for s in sidecar.symbols)
        
        if len(ast_symbols) == 0:
            api_coverage_score = 1.0 # Nothing to document
        else:
            # How many of the AST symbols are in the documented symbols?
            covered = ast_symbols.intersection(doc_symbols)
            api_coverage_score = len(covered) / len(ast_symbols)
    else:
        api_coverage_score = 0.5 # Unknown due to parse error
        
    # 4. Final Confidence Formula
    confidence = (0.5 * citation_score) + (0.3 * api_coverage_score) + (0.2 * template_score)
    
    print(f"    -> Validation for {file_path}: Template={template_score:.2f}, Citations={citation_score:.2f} ({valid_citations}/{total_citations}), API={api_coverage_score:.2f} => Confidence: {confidence:.2f}")
    
    return min(1.0, max(0.0, confidence))
