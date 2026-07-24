import os
import json
from jinja2 import Template
from langchain_openai import ChatOpenAI
from deep_rkb_agent.schemas import ArchitectureComponents, ArchitectureDataModels, ArchitectureLessons

PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "prompts")


def _load_prompt(name: str) -> Template:
    path = os.path.abspath(os.path.join(PROMPTS_DIR, name))
    with open(path, "r") as f:
        return Template(f.read())


def _get_llm():
    from deep_rkb_agent.llm_utils import get_llm
    return get_llm("complex")


def _load_ontology_concepts(repo_root: str) -> str:
    path = os.path.join(repo_root, "docs", "ontology", "concepts.md")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def _load_module_sidecars(repo_root: str) -> list:
    modules_dir = os.path.join(repo_root, "docs", "modules")
    sidecars = []
    if os.path.exists(modules_dir):
        for f in os.listdir(modules_dir):
            if f.endswith(".json"):
                try:
                    with open(os.path.join(modules_dir, f), "r", encoding="utf-8") as fh:
                        sidecars.append(json.load(fh))
                except Exception:
                    pass
    return sidecars


def synthesize_components(repo_root: str, critique: str = ""):
    print("  [Synthesizer] Building architecture components...")
    ontology_concepts = _load_ontology_concepts(repo_root)
    sidecars = _load_module_sidecars(repo_root)
    
    # Just pass the summaries to save context window
    module_summaries = []
    for s in sidecars:
        # Some symbols might have responsibility
        module_summaries.append({
            "module": s.get("module"),
            "source": s.get("source"),
            "symbols": [sym.get("name") for sym in s.get("symbols", [])]
        })
        
    template = _load_prompt("synthesizer_components.jinja2")
    prompt = template.render(
        ontology_concepts=ontology_concepts,
        modules_json=json.dumps(module_summaries, indent=2),
        critique=critique
    )
    
    llm = _get_llm()
    from deep_rkb_agent.llm_utils import robust_invoke
    result = robust_invoke(llm, prompt, ArchitectureComponents, repo_root, agent_name="Synthesizer")
    
    arch_dir = os.path.join(repo_root, "docs", "architecture")
    os.makedirs(arch_dir, exist_ok=True)
    out_path = os.path.join(arch_dir, "components.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(result.markdown_doc)
    print(f"  [Synthesizer] Wrote {out_path}")


def synthesize_models(repo_root: str, critique: str = ""):
    print("  [Synthesizer] Building architecture data models...")
    sidecars = _load_module_sidecars(repo_root)
    
    all_symbols = []
    for s in sidecars:
        for sym in s.get("symbols", []):
            sym_copy = sym.copy()
            sym_copy["module_source"] = s.get("source")
            all_symbols.append(sym_copy)
            
    template = _load_prompt("synthesizer_models.jinja2")
    prompt = template.render(
        symbols_json=json.dumps(all_symbols, indent=2),
        critique=critique
    )
    
    llm = _get_llm()
    from deep_rkb_agent.llm_utils import robust_invoke
    result = robust_invoke(llm, prompt, ArchitectureDataModels, repo_root, agent_name="Synthesizer")
    
    arch_dir = os.path.join(repo_root, "docs", "architecture")
    os.makedirs(arch_dir, exist_ok=True)
    out_path = os.path.join(arch_dir, "data-models.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(result.markdown_doc)
    print(f"  [Synthesizer] Wrote {out_path}")


def synthesize_lessons(repo_root: str):
    memory_path = os.path.join(repo_root, ".rkb", "memory.jsonl")
    
    # Only run if there is memory to process
    if not os.path.exists(memory_path) or os.path.getsize(memory_path) == 0:
        return
        
    print("  [Synthesizer] Building architecture lessons learned...")
    memory_entries = []
    with open(memory_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    memory_entries.append(json.loads(line))
                except Exception:
                    pass
                    
    template = _load_prompt("synthesizer_lessons.jinja2")
    prompt = template.render(
        memory_jsonl=json.dumps(memory_entries, indent=2)
    )
    
    llm = _get_llm()
    from deep_rkb_agent.llm_utils import robust_invoke
    result = robust_invoke(llm, prompt, ArchitectureLessons, repo_root, agent_name="Synthesizer")
    
    arch_dir = os.path.join(repo_root, "docs", "architecture")
    os.makedirs(arch_dir, exist_ok=True)
    out_path = os.path.join(arch_dir, "lessons_learned.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(result.markdown_doc)
    print(f"  [Synthesizer] Wrote {out_path}")


def run_synthesizer(repo_root: str, critique: str = "") -> bool:
    """
    Entry point for the synthesizer. Runs all synthesis tasks sequentially.
    Returns True if reciprocity mismatches were found and need reprocessing.
    """
    print("[Synthesizer] Starting synthesis...")
    # 1. Run LLM tasks
    try:
        synthesize_components(repo_root, critique)
        synthesize_models(repo_root, critique)
        synthesize_lessons(repo_root)
    except Exception as e:
        import traceback
        print(f"  [Synthesizer] Error in LLM synthesis: {e}\n{traceback.format_exc()}")
        
    # 2. Run Deterministic Reciprocity Check
    requires_reprocess = False
    try:
        from deep_rkb_agent.agents.reciprocity import run_reciprocity_check
        _, requires_reprocess = run_reciprocity_check(repo_root)
    except Exception as e:
        import traceback
        print(f"  [Synthesizer] Error in reciprocity check: {e}\n{traceback.format_exc()}")
        
    print("[Synthesizer] Complete.")
    return requires_reprocess
