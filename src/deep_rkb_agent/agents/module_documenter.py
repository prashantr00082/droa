import os
import json
from jinja2 import Template
from langchain_openai import ChatOpenAI
from deep_rkb_agent.schemas import ModuleSidecar
from deep_rkb_agent.tools.ast_parser import extract_symbols
from deep_rkb_agent.tools.file_reader import read_file_window

def _get_llm(ast_data: dict, file_content: str):
    """
    Heuristic model router for local inference servers.
    Routes to a complex model (GLM 5.2) if the file is large or has many symbols.
    Routes to a fast model (Qwen/Gemma) for simpler files.
    """
    # Count total classes and functions
    num_classes = len(ast_data.get('classes', []))
    num_functions = len(ast_data.get('functions', []))
    total_symbols = num_classes + num_functions
    num_lines = len(file_content.splitlines())
    
    if total_symbols > 5 or num_lines > 200:
        model = os.environ.get("LLM_MODEL_COMPLEX", "glm-5.2-fp8")
        base_url = os.environ.get("LLM_BASE_URL_COMPLEX", "http://localhost:8000/v1")
        api_key = os.environ.get("LLM_API_KEY_COMPLEX", "dummy")
        
        print(f"      [Router] Complex file detected ({total_symbols} symbols, {num_lines} lines). Routing to {model}.")
        return ChatOpenAI(
            model=model,
            base_url=base_url,
            api_key=api_key,
            temperature=0
        )
    else:
        model = os.environ.get("LLM_MODEL_SIMPLE", "Qwen/Qwen3-VL-235B-A22B-Instruct-FP8")
        base_url = os.environ.get("LLM_BASE_URL_SIMPLE", "http://localhost:8000/v1")
        api_key = os.environ.get("LLM_API_KEY_SIMPLE", "dummy")
        
        print(f"      [Router] Simple file detected ({total_symbols} symbols, {num_lines} lines). Routing to {model}.")
        return ChatOpenAI(
            model=model,
            base_url=base_url,
            api_key=api_key,
            temperature=0
        )

def document_module(repo_root: str, file_path: str) -> ModuleSidecar:
    """
    Documents a module using LangChain and ChatGoogleGenerativeAI.
    """
    abs_path = os.path.join(repo_root, file_path)
    
    # 1. Extract structural symbols via AST
    ast_data = extract_symbols(abs_path)
    
    # 2. Read file chunk (max 500 lines for MVP)
    file_content = read_file_window(abs_path, start_line=1, max_lines=500)
    
    # 3. Load and render prompt
    # Since main.py runs from the repo root, this path will be relative to repo_root
    prompt_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "prompts", "module_documenter.jinja2")
    
    # Fallback if run from a different CWD context
    if not os.path.exists(prompt_path):
        prompt_path = os.path.join(repo_root, "prompts", "module_documenter.jinja2")
        
    with open(prompt_path, "r") as f:
        template = Template(f.read())
        
    module_name_clean = file_path.replace(os.sep, "_").replace(".", "_")
    
    prompt_text = template.render(
        module_name=module_name_clean,
        ast_symbols=json.dumps(ast_data, indent=2),
        file_content=file_content
    )
    
    # 4. Invoke LLM with Structured Outputs
    llm = _get_llm(ast_data, file_content)
    structured_llm = llm.with_structured_output(ModuleSidecar)
    
    print(f"    -> Invoking LLM for {file_path}...")
    result: ModuleSidecar = structured_llm.invoke(prompt_text)
    
    return result
