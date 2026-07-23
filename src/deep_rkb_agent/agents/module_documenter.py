import os
import json
from typing import List
from langchain_openai import ChatOpenAI
from pydantic import BaseModel
from deep_rkb_agent.schemas import ModuleSidecar
from deep_rkb_agent.tools.ast_parser import extract_symbols

MAX_CHUNK_LINES = 300
OVERLAP_LINES = 50

class ModuleChunkSummary(BaseModel):
    chunk_index: int
    chunk_summary: str
    external_deps: List[str]
    extension_points: List[str]
    config_keys: List[str]
    symbol_names: List[str]
    citations: List[str]


def _get_llm(ast_data: dict, total_lines: int):
    """
    Heuristic model router for local inference servers.
    Routes to a complex model (GLM 5.2) if the file is large or has many symbols.
    Routes to a fast model (Qwen/Gemma) for simpler files.
    """
    # Count total classes and functions
    num_classes = len(ast_data.get('classes', []))
    num_functions = len(ast_data.get('functions', []))
    total_symbols = num_classes + num_functions
    num_lines = total_lines
    
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


def _read_all_lines(filepath: str) -> List[str]:
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.readlines()


def _build_file_chunks(lines: List[str], filepath: str, max_lines: int = MAX_CHUNK_LINES, overlap: int = OVERLAP_LINES) -> List[str]:
    total_lines = len(lines)
    if total_lines == 0:
        return [f"--- FILE: {filepath} | LINES 0-0 of 0 ---\n--- END OF WINDOW ---"]

    chunks = []
    start_idx = 0
    while start_idx < total_lines:
        end_idx = min(total_lines, start_idx + max_lines)
        numbered_lines = [f"{start_idx + i + 1:4d} | {line}" for i, line in enumerate(lines[start_idx:end_idx])]
        header = f"--- FILE: {filepath} | LINES {start_idx + 1}-{end_idx} of {total_lines} ---\n"
        footer = "\n--- END OF WINDOW ---"
        chunks.append(header + "".join(numbered_lines) + footer)
        if end_idx >= total_lines:
            break
        start_idx = max(0, end_idx - overlap)
    return chunks


def _summarize_chunk(llm, file_path: str, chunk_index: int, chunk_text: str) -> ModuleChunkSummary:
    prompt_text = (
        "You are an expert software architect analyzing one chunk of a module source file. "
        "The chunk below is part of the file and includes line-number citations. "
        "Return ONLY valid JSON matching the schema exactly.\n\n"
        "Schema fields:\n"
        "- chunk_index: the ordinal index of this chunk.\n"
        "- chunk_summary: a concise factual summary of this chunk.\n"
        "- external_deps: external libraries/packages imported or referenced in this chunk.\n"
        "- extension_points: classes/functions designed for extension or overriding in this chunk.\n"
        "- config_keys: configuration or environment variables read in this chunk.\n"
        "- symbol_names: top-level symbols defined or referenced in this chunk.\n"
        "- citations: all file:line citations used for assertions in chunk_summary.\n\n"
        f"FILE: {file_path}\n"
        f"CHUNK_INDEX: {chunk_index}\n\n"
        f"{chunk_text}"
    )
    from deep_rkb_agent.llm_utils import robust_invoke
    return robust_invoke(llm, prompt_text, ModuleChunkSummary)


def _build_module_prompt(module_name: str, ast_data: dict, chunk_summaries: List[ModuleChunkSummary], file_path: str) -> str:
    chunks_json = json.dumps([chunk.model_dump() for chunk in chunk_summaries], indent=2)
    return (
        "You are an expert software architect documenting a module from a repository. "
        "You have structured AST symbol information and chunk-level summaries of the file. "
        "Use only facts present in the AST data or the chunk summaries. Do not infer beyond the provided evidence.\n\n"
        "REQUIREMENTS:\n"
        "1. Populate the ModuleSidecar schema exactly.\n"
        "2. In markdown_doc, follow this Markdown template exactly:\n"
        "   # Module: {module_name}\n"
        "   ## Purpose\n"
        "   [Describe high-level purpose]\n\n"
        "   ## Responsibilities\n"
        "   [List core responsibilities]\n\n"
        "   ## Public API\n"
        "   [List exposed classes/functions]\n\n"
        "   ## Dependencies\n"
        "   [List external and internal dependencies]\n\n"
        "   ## Things To Know Before Editing\n"
        "   [Important gotchas or architectural constraints]\n\n"
        "3. Every factual claim in markdown_doc MUST carry a citation using [file:line].\n"
        "4. citations should align with the file path and line numbers in the provided chunk summaries.\n\n"
        "AST Symbols Extracted:\n"
        f"{json.dumps(ast_data, indent=2)}\n\n"
        "Chunk Summaries:\n"
        f"{chunks_json}\n"
    ).format(module_name=module_name)


def _merge_sidecar_fields(primary: ModuleSidecar, secondary: ModuleSidecar) -> ModuleSidecar:
    unique_symbols = {sym.name: sym for sym in primary.symbols}
    for sym in secondary.symbols:
        if sym.name not in unique_symbols:
            unique_symbols[sym.name] = sym
    primary.symbols = list(unique_symbols.values())

    primary.external_deps = sorted(set(primary.external_deps) | set(secondary.external_deps))
    primary.extension_points = sorted(set(primary.extension_points) | set(secondary.extension_points))
    primary.config_keys = sorted(set(primary.config_keys) | set(secondary.config_keys))
    primary.confidence = min(1.0, (primary.confidence + secondary.confidence) / 2)
    return primary


def document_module(repo_root: str, file_path: str) -> ModuleSidecar:
    """
    Documents a module using LangChain and ChatGoogleGenerativeAI.
    """
    abs_path = os.path.join(repo_root, file_path)
    
    # 1. Extract structural symbols via AST
    ast_data = extract_symbols(abs_path)
    
    # 2. Read the file in chunks so large files can be processed fully
    lines = _read_all_lines(abs_path)
    chunk_texts = _build_file_chunks(lines, abs_path)
    
    llm = _get_llm(ast_data, len(lines))
    chunk_summaries = []
    for idx, chunk_text in enumerate(chunk_texts, start=1):
        print(f"    -> Summarizing chunk {idx}/{len(chunk_texts)} for {file_path}...")
        chunk_summaries.append(_summarize_chunk(llm, file_path, idx, chunk_text))
    
    # 3. Build final prompt from AST and chunk summaries
    prompt_text = _build_module_prompt(
        module_name=file_path.replace(os.sep, "_").replace(".", "_"),
        ast_data=ast_data,
        chunk_summaries=chunk_summaries,
        file_path=file_path
    )
    
    print(f"    -> Invoking final module documentation model for {file_path}...")
    from deep_rkb_agent.llm_utils import robust_invoke
    result: ModuleSidecar = robust_invoke(llm, prompt_text, ModuleSidecar)
    
    return result
