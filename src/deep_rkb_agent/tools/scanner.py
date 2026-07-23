import os
import hashlib
from typing import List, Dict, Any

IGNORE_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".rkb", "docs", "tests", "prompts"}
SUPPORTED_EXTS = {".py", ".java", ".go"}
IGNORE_EXTS = {".pyc", ".tmp", ".log"}

def hash_file(filepath: str) -> str:
    hasher = hashlib.sha1()
    try:
        with open(filepath, 'rb') as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception:
        return ""

def scan_repository(repo_root: str) -> List[Dict[str, Any]]:
    tasks = []
    
    # 1. Ontology tasks (Global)
    tasks.append({
        "source": "repo_root",
        "output": "ontology/concepts.md",
        "category": "ontology.concepts",
        "priority": 100,
        "hash": ""
    })
    tasks.append({
        "source": "repo_root",
        "output": "ontology/relationships.md",
        "category": "ontology.relationships",
        "priority": 100,
        "hash": ""
    })
    tasks.append({
        "source": "repo_root",
        "output": "ontology/flows.md",
        "category": "ontology.flows",
        "priority": 100,
        "hash": ""
    })
    
    # 2. Module tasks
    for root, dirs, files in os.walk(repo_root):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith('.')]
        
        for file in files:
            _, ext = os.path.splitext(file)
            if ext not in SUPPORTED_EXTS or file.startswith('.'):
                continue
                
            filepath = os.path.join(root, file)
            rel_path = os.path.relpath(filepath, repo_root)
            
            # Basic chunking: treat each file as a module for now
            module_name = rel_path.replace(os.sep, "_").replace(".", "_")
            output_path = f"modules/{module_name}.md"
            
            tasks.append({
                "source": rel_path,
                "output": output_path,
                "category": "module",
                "priority": 50,
                "hash": hash_file(filepath)
            })
            
    return tasks
