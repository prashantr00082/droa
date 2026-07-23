import os
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain import hub
from langchain_core.prompts import PromptTemplate

class RuleExtraction(BaseModel):
    rule: str = Field(description="A single, generalized sentence rule extracted from the critique. Must be actionable.")

def _get_llm():
    base_url = os.environ.get("LLM_BASE_URL_COMPLEX", "http://localhost:8000/v1")
    api_key = os.environ.get("LLM_API_KEY_COMPLEX", "dummy")
    model = os.environ.get("LLM_MODEL_COMPLEX", "gpt-4")
    return ChatOpenAI(model=model, base_url=base_url, api_key=api_key, temperature=0)

def extract_and_store_rule(repo_root: str, critique: str):
    print("  [Memory Updater] Extracting rule from critique for Continual Learning...")
    
    prompt = f"""You are a Continual Learning agent. 
An adversarial reviewer just rejected an agent's output with this critique:
---
{critique}
---
Extract a single, generalized rule (1 sentence) that the agent should follow in the future to avoid this mistake.
Return ONLY valid JSON matching the requested schema."""

    llm = _get_llm()
    from deep_rkb_agent.llm_utils import robust_invoke
    
    try:
        result: RuleExtraction = robust_invoke(llm, prompt, RuleExtraction, repo_root)
        new_rule = result.rule
        print(f"  [Memory Updater] Extracted Rule: {new_rule}")
        
        # 2. Push to LangSmith Context Hub
        hub_path = os.environ.get("LANGSMITH_HUB_PATH", "droa/memory-rules")
        
        try:
            existing_prompt = hub.pull(hub_path)
            current_text = existing_prompt.template
        except Exception:
            current_text = "You are DROA. Follow these organizational rules:\n"
            
        new_text = current_text + f"\n- {new_rule}"
        new_prompt = PromptTemplate.from_template(new_text)
        
        try:
            hub.push(hub_path, new_prompt)
            print(f"  [Memory Updater] Successfully pushed rule to LangSmith Context Hub ({hub_path}).")
        except Exception as e:
            print(f"  [Memory Updater] Failed to push to LangSmith Context Hub. Saving locally instead. Error: {e}")
            local_path = os.path.join(repo_root, ".droa_memory.md")
            with open(local_path, "a", encoding="utf-8") as f:
                f.write(f"\n- {new_rule}")
                
    except Exception as e:
        print(f"  [Memory Updater] Failed to extract rule: {e}")
