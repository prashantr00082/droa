import os
from deep_rkb_agent.tools.ast_parser import extract_symbols
from deep_rkb_agent.tools.scanner import IGNORE_DIRS, IGNORE_EXTS, SUPPORTED_EXTS
from typing import Dict, List

def build_import_graph(repo_root: str) -> Dict[str, List[str]]:
    """
    Walks all Python files in repo_root and builds a dependency dict:
    { "relative/path/to/file.py": ["import_statement_1", ...], ... }
    
    This uses the AST parser's import extraction, which reads only structural data
    (import declarations), never method bodies.
    """
    graph: Dict[str, List[str]] = {}
    
    for root, dirs, files in os.walk(repo_root):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith('.')]
        
        for file in files:
            _, ext = os.path.splitext(file)
            if ext not in SUPPORTED_EXTS:
                continue
            
            abs_path = os.path.join(root, file)
            rel_path = os.path.relpath(abs_path, repo_root)
            
            symbols = extract_symbols(abs_path)
            if "error" not in symbols:
                graph[rel_path] = symbols.get("imports", [])
    
    return graph


def build_tree_summary(repo_root: str, max_depth: int = 3) -> str:
    """
    Produces a bounded, human-readable directory tree string, similar to `tree` command output.
    """
    lines = [f"{os.path.basename(repo_root)}/"]
    
    def _walk(path: str, prefix: str, depth: int):
        if depth > max_depth:
            return
        try:
            entries = sorted(os.listdir(path))
        except PermissionError:
            return
        
        entries = [e for e in entries
                   if e not in IGNORE_DIRS
                   and not e.startswith('.')
                   and not any(e.endswith(ext) for ext in IGNORE_EXTS)]
        
        for i, entry in enumerate(entries):
            is_last = (i == len(entries) - 1)
            connector = "└── " if is_last else "├── "
            child_path = os.path.join(path, entry)
            
            if os.path.isdir(child_path):
                lines.append(f"{prefix}{connector}{entry}/")
                extension = "    " if is_last else "│   "
                _walk(child_path, prefix + extension, depth + 1)
            else:
                lines.append(f"{prefix}{connector}{entry}")
    
    _walk(repo_root, "", 1)
    return "\n".join(lines)


def find_readmes(repo_root: str) -> str:
    """Find and read all README files at the root level."""
    content_parts = []
    for f in os.listdir(repo_root):
        if f.lower().startswith("readme") and f.endswith((".md", ".txt", ".rst")):
            abs_path = os.path.join(repo_root, f)
            try:
                with open(abs_path, 'r', encoding='utf-8') as fh:
                    content_parts.append(f"=== {f} ===\n{fh.read()}")
            except Exception:
                pass
    return "\n\n".join(content_parts) if content_parts else "(No README found)"


def find_entrypoints(repo_root: str) -> List[Dict]:
    """
    Find files that look like entrypoints:
    - Contain `if __name__ == "__main__":`
    - Named main.py, router.py, app.py, server.py, etc.
    Returns a list of {path, top_level_functions} dicts.
    """
    entrypoint_names = {"main.py", "app.py", "server.py", "router.py",
                        "controller.py", "api.py", "run.py", "cli.py",
                        "main.go", "main.java", "application.java"}
    results = []
    
    for root, dirs, files in os.walk(repo_root):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith('.')]
        
        for f in files:
            _, ext = os.path.splitext(f)
            if ext not in SUPPORTED_EXTS:
                continue
            abs_path = os.path.join(root, f)
            rel_path = os.path.relpath(abs_path, repo_root)
            is_entrypoint = f.lower() in entrypoint_names
            
            # Check if `__main__` guard exists
            try:
                with open(abs_path, 'r', encoding='utf-8') as fh:
                    content = fh.read()
                if '__name__' in content and '__main__' in content:
                    is_entrypoint = True
            except Exception:
                pass
            
            if is_entrypoint:
                symbols = extract_symbols(abs_path)
                results.append({
                    "path": rel_path,
                    "functions": symbols.get("functions", []),
                    "classes": symbols.get("classes", []),
                    "imports": symbols.get("imports", []),
                })
    
    return results
