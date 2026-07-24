import os
from pydantic import BaseModel, Field
from deep_rkb_agent.llm_utils import get_llm

class RuleExtraction(BaseModel):
    agent_target: str = Field(description="The specific agent this rule applies to (e.g. 'Synthesizer', 'ModuleDocumenter', 'Cartographer', 'Reviewer', or 'GLOBAL').")
    rule: str = Field(description="A single, generalized sentence rule extracted from the critique. Must be actionable.")

def extract_and_store_rule(repo_root: str, critique: str):
    print("  [Memory Updater] Extracting rule from critique for Continual Learning...")
    
    prompt = f"""
    You are a meta-learning agent analyzing a critique from an adversarial code reviewer.
    The reviewer has rejected an agent's documentation. 
    
    1. Extract the core lesson from this critique.
    2. Determine which agent made the mistake (ModuleDocumenter, Synthesizer, Cartographer, Reviewer) or if it's a GLOBAL rule.
    
    CRITIQUE:
    {critique}
    Return ONLY valid JSON matching the requested schema."""

    llm = get_llm("complex")
    from deep_rkb_agent.llm_utils import robust_invoke
    
    try:
        result: RuleExtraction = robust_invoke(llm, prompt, RuleExtraction, repo_root)
        new_rule = result.rule.replace('\n', ' ').strip()
        target = result.agent_target
        print(f"  [Memory Updater] Extracted Rule for [{target}]: {new_rule}")
        
        # Save to Local File
        mem_path = os.path.join(repo_root, ".droa_memory.md")
        with open(mem_path, "a", encoding="utf-8") as f:
            f.write(f"[{target}] {new_rule}\n")
            
        print(f"  [Memory Updater] Successfully appended rule to local memory ({mem_path}).")
        
    except Exception as e:
        print(f"  [Memory Updater] Failed to extract or store rule: {e}")
