from deep_rkb_agent.logger import get_logger
logger = get_logger('Reciprocity')
import os
import json
from typing import Dict, List, Tuple
from deep_rkb_agent.db import add_tasks

def run_reciprocity_check(repo_root: str) -> Tuple[str, bool]:
    """
    Reads all JSON sidecars in docs/modules/ and verifies that if Module A claims to depend on Module B,
    Module B acknowledges being used by Module A.
    Generates docs/architecture/reciprocity_report.md and inserts tasks to auto-resolve mismatches.
    Returns (report_path, requires_reprocess).
    """
    logger.info("  [Synthesizer] Running Reciprocity Check...")
    modules_dir = os.path.join(repo_root, "docs", "modules")
    
    # Load all module sidecars
    sidecars = {}
    if os.path.exists(modules_dir):
        for f in os.listdir(modules_dir):
            if f.endswith('.json'):
                try:
                    with open(os.path.join(modules_dir, f), 'r', encoding="utf-8") as fh:
                        data = json.load(fh)
                        sidecars[data.get('source', f)] = data
                except Exception:
                    pass
                    
    # Build maps
    # claims_depends_on: { "module_A": ["module_B", "module_C"] }
    # claims_used_by: { "module_A": ["module_X"] }
    claims_depends_on = {}
    claims_used_by = {}
    
    for src, data in sidecars.items():
        deps = set()
        users = set()
        for sym in data.get('symbols', []):
            deps.update(sym.get('depends_on', []))
            users.update(sym.get('used_by', []))
        
        # Clean up the claims to match filenames (heuristic)
        cleaned_deps = set([d for d in deps if d in sidecars])
        cleaned_users = set([u for u in users if u in sidecars])
        
        claims_depends_on[src] = cleaned_deps
        claims_used_by[src] = cleaned_users

    # Check for mismatches
    missing_acknowledgments = []
    
    for src_a, deps_of_a in claims_depends_on.items():
        for module_b in deps_of_a:
            if src_a not in claims_used_by.get(module_b, set()):
                missing_acknowledgments.append({
                    "from": src_a,
                    "to": module_b,
                    "issue": f"`{src_a}` claims to depend on `{module_b}`, but `{module_b}` does not list `{src_a}` in its `used_by`."
                })
                
    for src_a, users_of_a in claims_used_by.items():
        for module_b in users_of_a:
            if src_a not in claims_depends_on.get(module_b, set()):
                missing_acknowledgments.append({
                    "from": src_a,
                    "to": module_b,
                    "issue": f"`{src_a}` claims it is used by `{module_b}`, but `{module_b}` does not list `{src_a}` in its `depends_on`."
                })
                
    # Generate Report
    report = "# Architecture: Reciprocity Report\n\n"
    report += "This report validates the cross-module dependency claims made by the Module Documenters.\n\n"
    
    new_tasks = []
    if not missing_acknowledgments:
        report += "✅ **All claims are reciprocal and correct.**\n"
    else:
        report += "⚠️ **Inconsistencies Found:**\n\n"
        for i, issue in enumerate(missing_acknowledgments, 1):
            report += f"{i}. {issue['issue']}\n"
            new_tasks.append({
                "source": issue["from"],
                "category": "module",
                "output": f"modules/{issue['from']}.md",
                "priority": 100,
                "notes": f"Reciprocity mismatch: {issue['issue']} Please fix this."
            })
            new_tasks.append({
                "source": issue["to"],
                "category": "module",
                "output": f"modules/{issue['to']}.md",
                "priority": 100,
                "notes": f"Reciprocity mismatch: {issue['issue']} Please fix this."
            })
            
    if new_tasks:
        logger.info(f"  [Synthesizer] Found {len(missing_acknowledgments)} mismatches. Auto-queueing {len(new_tasks)} resolution tasks.")
        add_tasks(repo_root, new_tasks)
            
    arch_dir = os.path.join(repo_root, "docs", "architecture")
    os.makedirs(arch_dir, exist_ok=True)
    report_path = os.path.join(arch_dir, "reciprocity_report.md")
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
        
    logger.info(f"  [Synthesizer] Wrote {report_path}")
    return report_path, len(missing_acknowledgments) > 0
