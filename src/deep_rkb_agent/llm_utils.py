from deep_rkb_agent.logger import get_logger
logger = get_logger('LLMUtils')
import re
from pydantic import BaseModel
from langchain_core.output_parsers import PydanticOutputParser

import os

def get_llm(tier: str = "complex"):
    """
    Centralized LLM factory.
    If USE_HF=true, uses Hugging Face Inference Endpoints as a free fallback.
    Otherwise, uses the local/proxy OpenAI-compatible endpoint.
    """
    use_hf = os.environ.get("USE_HF", "false").lower() == "true"
    
    if use_hf:
        try:
            from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
        except ImportError:
            raise ImportError("Please install langchain-huggingface to use the HF fallback: pip install langchain-huggingface")
            
        if tier == "complex":
            model_id = os.environ.get("HF_MODEL_COMPLEX", "Qwen/Qwen2.5-72B-Instruct")
        else:
            model_id = os.environ.get("HF_MODEL_SIMPLE", "Qwen/Qwen2.5-7B-Instruct")
            
        hf_token = os.environ.get("HF_TOKEN")
        if not hf_token:
            raise ValueError("HF_TOKEN environment variable must be set when USE_HF=true")
            
        llm = HuggingFaceEndpoint(
            repo_id=model_id,
            task="text-generation",
            huggingfacehub_api_token=hf_token,
            temperature=0.1,
            max_new_tokens=4096
        )
        return ChatHuggingFace(llm=llm)
    else:
        from langchain_openai import ChatOpenAI
        if tier == "complex":
            model = os.environ.get("LLM_MODEL_COMPLEX", "glm-5.2-fp8")
            base_url = os.environ.get("LLM_BASE_URL_COMPLEX", "http://localhost:8000/v1")
            api_key = os.environ.get("LLM_API_KEY_COMPLEX", "dummy")
        else:
            model = os.environ.get("LLM_MODEL_SIMPLE", "Qwen/Qwen3-VL-235B-A22B-Instruct-FP8")
            base_url = os.environ.get("LLM_BASE_URL_SIMPLE", "http://localhost:8000/v1")
            api_key = os.environ.get("LLM_API_KEY_SIMPLE", "dummy")
            
        if not api_key:
            raise RuntimeError("LLM API key is missing. Please set the appropriate environment variable.")
            
        return ChatOpenAI(
            model=model,
            base_url=base_url,
            api_key=api_key,
            temperature=0,
            max_tokens=int(os.environ.get("LLM_MAX_TOKENS", 16384))
        )


def get_organization_memory(repo_root: str, agent_name: str = "GLOBAL") -> str:
    """Reads the organization memory constraints from the local file, filtering by target agent."""
    if not repo_root:
        return ""
        
    memory_lines = []
    mem_path = os.path.join(repo_root, ".droa_memory.md")
    if os.path.exists(mem_path):
        with open(mem_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("[GLOBAL]") or line.startswith(f"[{agent_name}]"):
                    memory_lines.append(line)
                
    if memory_lines:
        return "\n\n<ORGANIZATION_MEMORY>\n" + "\n".join(memory_lines) + "\n</ORGANIZATION_MEMORY>\n"
    return ""

def robust_invoke(llm, prompt_text: str, schema_class, repo_root: str = None, agent_name: str = "GLOBAL"):
    """
    Attempts to use native structured output, but falls back to manual prompt injection
    and regex JSON extraction if the open-source proxy model fails to follow strict tool calling.
    """
    # Append memory to prompt if available
    memory = get_organization_memory(repo_root, agent_name)
    if memory:
        prompt_text += memory

    # Check if we should force manual extraction (defaults to true for GLM/open-source models)
    force_manual = os.environ.get("FORCE_MANUAL_JSON", "true").lower() == "true"
    
    if not force_manual:
        # Try native structured output first
        try:
            structured_llm = llm.with_structured_output(schema_class)
            return structured_llm.invoke(prompt_text)
        except Exception as native_e:
            logger.error(f"      [Robust Parser] Native structured output failed: {native_e}")
            logger.info("      [Robust Parser] Falling back to manual JSON extraction...")
            
    # Manual JSON extraction path
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
    
    # Attempt to extract JSON from markdown code blocks or raw text
    import re
    match = re.search(r'```(?:json)?\n?(.*?)\n?```', text, re.DOTALL | re.IGNORECASE)
    if match:
        text = match.group(1).strip()
    else:
        # Fallback to finding outermost brackets
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1:
            text = text[start:end+1]
            
    if not text:
        logger.error(f"      [Robust Parser] FATAL: LLM returned an empty response.")
        raise ValueError("LLM returned an empty response.")
        
    try:
        return schema_class.model_validate_json(text)
    except Exception as e:
        # If it still fails, print the raw output so the user can debug what the LLM did
        logger.error(f"      [Robust Parser] FATAL: Failed to parse JSON even after fallback.")
        logger.info(f"      [Robust Parser] Raw LLM Output:\n{text}")
        raise e
