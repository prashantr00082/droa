import os
import json
from jinja2 import Template
from langchain_openai import ChatOpenAI

from deep_rkb_agent.schemas import OntologyConcepts, OntologyRelationships, OntologyFlows, OntologyOrganization
from deep_rkb_agent.tools.ast_parser import extract_symbols
from deep_rkb_agent.tools.import_graph import build_import_graph, build_tree_summary, find_readmes, find_entrypoints

PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "prompts")


def _load_prompt(name: str) -> Template:
    """Load a jinja2 prompt template by filename."""
    path = os.path.abspath(os.path.join(PROMPTS_DIR, name))
    with open(path, "r", encoding="utf-8") as f:
        return Template(f.read())


def _get_llm():
    from deep_rkb_agent.llm_utils import get_llm
    return get_llm("complex")


def _collect_all_symbols(repo_root: str) -> dict:
    """
    Walk every Python file and gather only top-level class and function names.
    This gives the LLM structural signal without feeding it any method bodies.
    """
    result = {}
    from deep_rkb_agent.tools.scanner import IGNORE_DIRS, IGNORE_EXTS
    for root, dirs, files in os.walk(repo_root):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith('.')]
        for f in files:
            if not f.endswith('.py'):
                continue
            abs_path = os.path.join(root, f)
            rel_path = os.path.relpath(abs_path, repo_root)
            symbols = extract_symbols(abs_path)
            if "error" not in symbols:
                result[rel_path] = {
                    "classes": symbols.get("classes", []),
                    "functions": symbols.get("functions", []),
                }
    return result


def build_concepts(repo_root: str) -> OntologyConcepts:
    """Sub-task: document domain vocabulary and key abstractions."""
    print("  [Cartographer] Building concepts...")
    tree = build_tree_summary(repo_root)
    readme = find_readmes(repo_root)
    all_symbols = _collect_all_symbols(repo_root)

    template = _load_prompt("cartographer_concepts.jinja2")
    prompt = template.render(
        tree=tree,
        readme=readme,
        all_symbols=json.dumps(all_symbols, indent=2)
    )

    llm = _get_llm()
    from deep_rkb_agent.llm_utils import robust_invoke
    result: OntologyConcepts = robust_invoke(llm, prompt, OntologyConcepts, repo_root, agent_name="Cartographer")
    return result


def build_relationships(repo_root: str) -> OntologyRelationships:
    """Sub-task: map module dependencies from the import graph."""
    print("  [Cartographer] Building relationships...")
    import_graph = build_import_graph(repo_root)

    template = _load_prompt("cartographer_relationships.jinja2")
    prompt = template.render(import_graph=json.dumps(import_graph, indent=2))

    llm = _get_llm()
    from deep_rkb_agent.llm_utils import robust_invoke
    result: OntologyRelationships = robust_invoke(llm, prompt, OntologyRelationships, repo_root, agent_name="Cartographer")
    return result


def build_flows(repo_root: str) -> OntologyFlows:
    """Sub-task: infer request/data flows from entrypoints and imports."""
    print("  [Cartographer] Building flows...")
    entrypoints = find_entrypoints(repo_root)
    import_graph = build_import_graph(repo_root)

    template = _load_prompt("cartographer_flows.jinja2")
    prompt = template.render(
        entrypoints=json.dumps(entrypoints, indent=2),
        import_graph=json.dumps(import_graph, indent=2)
    )

    llm = _get_llm()
    from deep_rkb_agent.llm_utils import robust_invoke
    result: OntologyFlows = robust_invoke(llm, prompt, OntologyFlows, repo_root, agent_name="Cartographer")
    return result


def build_organization(repo_root: str) -> OntologyOrganization:
    """Sub-task: map organization structure and ownership from CODEOWNERS."""
    print("  [Cartographer] Building organization ontology...")
    tree = build_tree_summary(repo_root)
    
    codeowners_content = ""
    for loc in ["CODEOWNERS", ".github/CODEOWNERS", "docs/CODEOWNERS"]:
        p = os.path.join(repo_root, loc)
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                codeowners_content += f"=== {loc} ===\n" + f.read() + "\n"
    if not codeowners_content:
        codeowners_content = "(No CODEOWNERS found)"

    template = _load_prompt("cartographer_org.jinja2")
    prompt = template.render(
        tree=tree,
        codeowners=codeowners_content
    )

    llm = _get_llm()
    from deep_rkb_agent.llm_utils import robust_invoke
    result: OntologyOrganization = robust_invoke(llm, prompt, OntologyOrganization, repo_root, agent_name="Cartographer")
    return result


def run_cartographer(repo_root: str, sub_task: str) -> str:
    """
    Entry point for the conductor. Routes to the correct sub-task.
    Returns the markdown content that was saved.
    """
    ontology_dir = os.path.join(repo_root, "docs", "ontology")
    os.makedirs(ontology_dir, exist_ok=True)

    if sub_task == "ontology.concepts":
        result = build_concepts(repo_root)
        out_path = os.path.join(ontology_dir, "concepts.md")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(result.markdown_doc)
        print(f"  [Cartographer] Wrote {out_path}")
        return result.markdown_doc

    elif sub_task == "ontology.relationships":
        result = build_relationships(repo_root)
        out_path = os.path.join(ontology_dir, "relationships.md")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(result.markdown_doc)
        # Also save machine-readable edges
        edges_path = os.path.join(ontology_dir, "dependency-graph.json")
        with open(edges_path, "w", encoding="utf-8") as f:
            json.dump(result.dependency_edges, f, indent=2)
        print(f"  [Cartographer] Wrote {out_path} and {edges_path}")
        return result.markdown_doc

    elif sub_task == "ontology.flows":
        result = build_flows(repo_root)
        out_path = os.path.join(ontology_dir, "flows.md")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(result.markdown_doc)
        print(f"  [Cartographer] Wrote {out_path}")
        return result.markdown_doc

    elif sub_task == "ontology.organization":
        result = build_organization(repo_root)
        out_path = os.path.join(ontology_dir, "organization.md")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(result.markdown_doc)
        print(f"  [Cartographer] Wrote {out_path}")
        return result.markdown_doc

    else:
        raise ValueError(f"Unknown Cartographer sub-task: {sub_task}")
