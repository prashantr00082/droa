import os
from jinja2 import Template

from deep_rkb_agent.schemas import ReviewResult

PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "prompts")

def _load_prompt(name: str) -> Template:
    path = os.path.abspath(os.path.join(PROMPTS_DIR, name))
    with open(path, "r", encoding="utf-8") as f:
        return Template(f.read())

def _get_llm():
    from deep_rkb_agent.llm_utils import get_llm
    return get_llm("complex")

def run_reviewer(repo_root: str) -> ReviewResult:
    print("  [Reviewer] Starting Adversarial Verification...")
    
    # Read generated outputs
    arch_dir = os.path.join(repo_root, "docs", "architecture")
    components_path = os.path.join(arch_dir, "components.md")
    models_path = os.path.join(arch_dir, "data-models.md")
    
    components_doc = ""
    models_doc = ""
    
    if os.path.exists(components_path):
        with open(components_path, "r", encoding="utf-8") as f:
            components_doc = f.read()
    if os.path.exists(models_path):
        with open(models_path, "r", encoding="utf-8") as f:
            models_doc = f.read()
            
    template = _load_prompt("reviewer.jinja2")
    prompt = template.render(
        components_doc=components_doc,
        models_doc=models_doc
    )
    
    llm = _get_llm()
    from deep_rkb_agent.llm_utils import robust_invoke
    result: ReviewResult = robust_invoke(llm, prompt, ReviewResult, repo_root, agent_name="Reviewer")
    
    if not result.approved:
        print(f"  [Reviewer] Found flaws! Critique: {result.critique[:100]}...")
    else:
        print(f"  [Reviewer] Architecture documentation approved!")
        
    return result
