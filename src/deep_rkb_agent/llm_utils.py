import re
from pydantic import BaseModel
from langchain_core.output_parsers import PydanticOutputParser

import os

def get_organization_memory(repo_root: str) -> str:
    """Reads the organization memory constraints from LangSmith Context Hub, falling back to local file."""
    if not repo_root:
        return ""
        
    memory_content = ""
    
    # 1. Try LangSmith Context Hub
    try:
        from langchain import hub
        hub_path = os.environ.get("LANGSMITH_HUB_PATH", "droa/memory-rules")
        prompt = hub.pull(hub_path)
        memory_content = prompt.template
    except Exception:
        pass
        
    # 2. Try Local File
    if not memory_content:
        mem_path = os.path.join(repo_root, ".droa_memory.md")
        if os.path.exists(mem_path):
            with open(mem_path, "r", encoding="utf-8") as f:
                memory_content = f.read()
                
    if memory_content:
        return "\n\n<ORGANIZATION_MEMORY>\n" + memory_content + "\n</ORGANIZATION_MEMORY>\n"
    return ""

def robust_invoke(llm, prompt_text: str, schema_class, repo_root: str = None):
    """
    Attempts to use native structured output, but falls back to manual prompt injection
    and regex JSON extraction if the open-source proxy model fails to follow strict tool calling.
    """
    # Append memory to prompt if available
    memory = get_organization_memory(repo_root)
    if memory:
        prompt_text += memory

    # Try native structured output first
    try:
        structured_llm = llm.with_structured_output(schema_class)
        return structured_llm.invoke(prompt_text)
    except Exception as native_e:
        print(f"      [Robust Parser] Native structured output failed: {native_e}")
        print("      [Robust Parser] Falling back to manual JSON extraction...")
        
        parser = PydanticOutputParser(pydantic_object=schema_class)
        instructions = parser.get_format_instructions()
        
        full_prompt = (
            prompt_text + 
            "\n\nCRITICAL: You MUST output ONLY a valid JSON object matching the following schema. "
            "Do not include any conversational text or markdown outside of the JSON block.\n\n" + 
            instructions
        )
        
        response = llm.invoke(full_prompt)
        text = response.content.strip()
        
        # Attempt to extract JSON from markdown code blocks if present
        match = re.search(r'```(?:json)?(.*?)```', text, re.DOTALL | re.IGNORECASE)
        if match:
            text = match.group(1).strip()
            
        try:
            return schema_class.model_validate_json(text)
        except Exception as e:
            # If it still fails, print the raw output so the user can debug what the LLM did
            print(f"      [Robust Parser] FATAL: Failed to parse JSON even after fallback.")
            print(f"      [Robust Parser] Raw LLM Output:\n{text}")
            raise e
