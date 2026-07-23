import os
import sqlite3
import time
from typing import TypedDict, Literal, Optional
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver

from deep_rkb_agent.db import init_db, add_tasks, claim_next_task, mark_task_complete, export_progress, requeue_task, claim_next_batch
from deep_rkb_agent.tools.scanner import scan_repository
from deep_rkb_agent.agents.module_documenter import document_module
from deep_rkb_agent.agents.validator import validate_module
from deep_rkb_agent.agents.cartographer import run_cartographer
from deep_rkb_agent.agents.synthesizer import run_synthesizer
from concurrent.futures import ThreadPoolExecutor, as_completed

class RKBState(TypedDict):
    repo_root: str
    phase: Literal["init", "scan", "process", "synthesize", "done"]
    batch_count: int

def init_node(state: RKBState) -> dict:
    print("[Conductor] Running init...")
    init_db(state["repo_root"])
    return {"phase": "scan"}

def scan_node(state: RKBState) -> dict:
    print("[Conductor] Running scan...")
    tasks = scan_repository(state["repo_root"])
    add_tasks(state["repo_root"], tasks)
    export_progress(state["repo_root"])
    return {"phase": "process"}

def _process_single_task(repo_root: str, task: dict):
    print(f"[Conductor] Claimed task {task['id']}: {task['source']} ({task['category']})")
    
    if task['category'] == 'module':
        try:
            sidecar = document_module(repo_root, task['source'])
            
            # Save Markdown
            docs_dir = os.path.join(repo_root, "docs", "modules")
            os.makedirs(docs_dir, exist_ok=True)
            
            md_path = os.path.join(repo_root, "docs", task['output'])
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(sidecar.markdown_doc)
                
            # Save JSON Sidecar
            json_path = md_path.replace(".md", ".json")
            with open(json_path, "w", encoding="utf-8") as f:
                sidecar_dict = sidecar.model_dump(exclude={"markdown_doc"})
                import json
                json.dump(sidecar_dict, f, indent=2)
                
            # Run Validator
            confidence = validate_module(repo_root, task['source'], sidecar.markdown_doc, sidecar)
            
            if confidence < 0.75 and task['priority'] < 60:
                print(f"    -> Low confidence ({confidence:.2f}). Re-queuing task {task['id']}...")
                requeue_task(repo_root, task['id'])
            else:
                if confidence < 0.75:
                    print(f"    -> Low confidence ({confidence:.2f}), but max retries reached. Marking complete.")
                mark_task_complete(repo_root, task['id'], confidence=confidence)
                
        except Exception as e:
            print(f"    -> Error processing {task['source']}: {e}")
            mark_task_complete(repo_root, task['id'], confidence=0.0)
            
    elif task['category'].startswith('ontology.'):
        try:
            run_cartographer(repo_root, task['category'])
            mark_task_complete(repo_root, task['id'], confidence=1.0)
        except Exception as e:
            print(f"    -> Error in Cartographer for {task['category']}: {e}")
            mark_task_complete(repo_root, task['id'], confidence=0.0)
    else:
        print(f"    -> Unknown category '{task['category']}', skipping.")
        mark_task_complete(repo_root, task['id'], confidence=0.5)

def process_node(state: RKBState) -> dict:
    # Claim up to 5 tasks at once for parallel processing
    tasks = claim_next_batch(state["repo_root"], limit=5)
    if not tasks:
        return {"phase": "synthesize"}
        
    print(f"[Conductor] Processing batch of {len(tasks)} tasks concurrently...")
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(_process_single_task, state["repo_root"], task) for task in tasks]
        for future in as_completed(futures):
            future.result() # Will raise any unhandled exceptions
            
    export_progress(state["repo_root"])
    
    return {"batch_count": state.get("batch_count", 0) + 1}

from deep_rkb_agent.agents.graph_exporter import export_to_cypher

def synthesize_node(state: RKBState) -> dict:
    print("[Conductor] Running synthesize...")
    requires_reprocess = run_synthesizer(state["repo_root"])
    export_to_cypher(state["repo_root"])
    
    if requires_reprocess:
        print("[Conductor] Reciprocity mismatches found! Looping back to process node.")
        return {"phase": "process"}
        
    return {"phase": "done"}

def router(state: RKBState) -> str:
    if state.get("phase") == "done":
        return "done"
    elif state.get("phase") == "synthesize":
        return "synthesize"
    elif state.get("phase") == "process":
        return "process"
    
    return "process"

def build_graph():
    g = StateGraph(RKBState)
    g.add_node("init", init_node)
    g.add_node("scan", scan_node)
    g.add_node("process", process_node)
    g.add_node("synthesize", synthesize_node)
    
    g.set_entry_point("init")
    g.add_edge("init", "scan")
    g.add_edge("scan", "process")
    g.add_conditional_edges("process", router, {"process": "process", "synthesize": "synthesize", "done": END})
    g.add_edge("synthesize", END)
    
    return g

def run_agent(repo_root: str):
    repo_root = os.path.abspath(repo_root)
    db_path = os.path.join(repo_root, ".rkb", "checkpoint.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    with SqliteSaver.from_conn_string(db_path) as checkpointer:
        g = build_graph()
        app = g.compile(checkpointer=checkpointer)
        
        config = {"configurable": {"thread_id": "main_run"}}
        
        print(f"Starting agent on {repo_root}...")
        try:
            for event in app.stream({"repo_root": repo_root, "batch_count": 0, "phase": "init"}, config, stream_mode="values"):
                pass
            print("[Conductor] Finished all tasks.")
            
            # Export the agent workflow
            try:
                ontology_dir = os.path.join(repo_root, "docs", "ontology")
                os.makedirs(ontology_dir, exist_ok=True)
                workflow_path = os.path.join(ontology_dir, "agent_workflow.md")
                mermaid_str = app.get_graph().draw_mermaid()
                with open(workflow_path, "w", encoding="utf-8") as f:
                    f.write(f"# Agent Workflow\n\n```mermaid\n{mermaid_str}\n```")
                print(f"[Conductor] Exported agent workflow to {workflow_path}")
            except Exception as e:
                print(f"[Conductor] Could not export agent workflow diagram: {e}")
        except KeyboardInterrupt:
            print("\n[Conductor] Interrupted! State is saved. Run again to resume.")
