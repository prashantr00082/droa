from deep_rkb_agent.logger import get_logger
logger = get_logger('Conductor')
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
    phase: Literal["init", "scan", "process", "synthesize", "review", "done"]
    batch_count: int
    critique: str
    review_count: int
    org: Optional[str]
    subsystem: Optional[str]
    service: Optional[str]

def init_node(state: RKBState) -> dict:
    logger.info("[Conductor] Running init...")
    init_db(state["repo_root"])
    return {"phase": "scan"}

def scan_node(state: RKBState) -> dict:
    logger.info("[Conductor] Running scan...")
    tasks = scan_repository(state["repo_root"])
    add_tasks(state["repo_root"], tasks)
    export_progress(state["repo_root"])
    return {"phase": "process"}

def _process_single_task(repo_root: str, task: dict):
    logger.info(f"[Conductor] Claimed task {task['id']}: {task['source']} ({task['category']})")
    
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
                logger.info(f"    -> Low confidence ({confidence:.2f}). Re-queuing task {task['id']}...")
                requeue_task(repo_root, task['id'])
            else:
                if confidence < 0.75:
                    logger.info(f"    -> Low confidence ({confidence:.2f}), but max retries reached. Marking complete.")
                mark_task_complete(repo_root, task['id'], confidence=confidence)
                
        except Exception as e:
            logger.error(f"    -> Error processing {task['source']}: {e}")
            if task['priority'] < 60:
                logger.info(f"    -> Re-queuing task {task['id']} due to error...")
                requeue_task(repo_root, task['id'])
            else:
                logger.info(f"    -> Max retries reached after errors. Marking complete.")
                mark_task_complete(repo_root, task['id'], confidence=0.0)
            
    elif task['category'].startswith('ontology.'):
        try:
            run_cartographer(repo_root, task['category'])
            mark_task_complete(repo_root, task['id'], confidence=1.0)
        except Exception as e:
            logger.error(f"    -> Error in Cartographer for {task['category']}: {e}")
            if task['priority'] < 60:
                logger.info(f"    -> Re-queuing task {task['id']} due to error...")
                requeue_task(repo_root, task['id'])
            else:
                logger.info(f"    -> Max retries reached after errors. Marking complete.")
                mark_task_complete(repo_root, task['id'], confidence=0.0)
    else:
        logger.info(f"    -> Unknown category '{task['category']}', skipping.")
        mark_task_complete(repo_root, task['id'], confidence=0.5)

def process_node(state: RKBState) -> dict:
    # Claim up to 5 tasks at once for parallel processing
    tasks = claim_next_batch(state["repo_root"], limit=5)
    if not tasks:
        return {"phase": "synthesize"}
        
    logger.info(f"[Conductor] Processing batch of {len(tasks)} tasks concurrently...")
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(_process_single_task, state["repo_root"], task) for task in tasks]
        for future in as_completed(futures):
            try:
                future.result() # Will raise any unhandled exceptions
            except Exception as e:
                logger.error(f"[Conductor] CRITICAL ERROR: Unhandled exception in task executor: {e}")
            
    export_progress(state["repo_root"])
    
    return {"batch_count": state.get("batch_count", 0) + 1}

from deep_rkb_agent.agents.graph_exporter import export_to_cypher

def synthesize_node(state: RKBState) -> dict:
    logger.info("[Conductor] Running synthesize...")
    requires_reprocess = run_synthesizer(state["repo_root"], critique=state.get("critique", ""))
    export_to_cypher(state["repo_root"], state.get("org"), state.get("subsystem"), state.get("service"))
    
    if requires_reprocess:
        logger.info("[Conductor] Reciprocity mismatches found! Looping back to process node.")
        return {"phase": "process"}
        
    return {"phase": "review"}

def review_node(state: RKBState) -> dict:
    logger.info("[Conductor] Running adversarial review...")
    from deep_rkb_agent.agents.reviewer import run_reviewer
    result = run_reviewer(state["repo_root"])
    
    if result.approved:
        return {"phase": "done", "critique": ""}
    else:
        review_count = state.get("review_count", 0)
        
        # Continual Learning: extract and store a rule from the critique
        from deep_rkb_agent.agents.memory_updater import extract_and_store_rule
        extract_and_store_rule(state["repo_root"], result.critique)
        
        if review_count >= 2:
            logger.info("[Conductor] Max review loops reached (2). Forcing done to prevent infinite loops.")
            return {"phase": "done", "critique": ""}
        else:
            logger.info("[Conductor] Reviewer found flaws. Looping back to synthesize.")
            return {"phase": "synthesize", "critique": result.critique, "review_count": review_count + 1}

def router(state: RKBState) -> str:
    if state.get("phase") == "done":
        return "done"
    elif state.get("phase") == "review":
        return "review"
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
    g.add_node("review", review_node)
    
    g.set_entry_point("init")
    g.add_edge("init", "scan")
    g.add_edge("scan", "process")
    g.add_conditional_edges("process", router, {"process": "process", "synthesize": "synthesize", "done": END})
    g.add_edge("synthesize", "review")
    g.add_conditional_edges("review", router, {"synthesize": "synthesize", "done": END})
    
    return g

def run_agent(repo_root: str, org: str = None, subsystem: str = None, service: str = None):
    repo_root = os.path.abspath(repo_root)
    db_path = os.path.join(repo_root, ".rkb", "checkpoint.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    with SqliteSaver.from_conn_string(db_path) as checkpointer:
        g = build_graph()
        app = g.compile(checkpointer=checkpointer)
        
        config = {"configurable": {"thread_id": "main_run"}}
        
        logger.info(f"Starting agent on {repo_root}...")
        try:
            initial_state = {
                "repo_root": repo_root,
                "batch_count": 0,
                "phase": "init",
                "org": org,
                "subsystem": subsystem,
                "service": service
            }
            for event in app.stream(initial_state, config, stream_mode="values"):
                pass
            logger.info("[Conductor] Finished all tasks.")
            
            # Export the agent workflow
            try:
                ontology_dir = os.path.join(repo_root, "docs", "ontology")
                os.makedirs(ontology_dir, exist_ok=True)
                workflow_path = os.path.join(ontology_dir, "agent_workflow.md")
                mermaid_str = app.get_graph().draw_mermaid()
                with open(workflow_path, "w", encoding="utf-8") as f:
                    f.write(f"# Agent Workflow\n\n```mermaid\n{mermaid_str}\n```")
                logger.info(f"[Conductor] Exported agent workflow to {workflow_path}")
            except Exception as e:
                logger.info(f"[Conductor] Could not export agent workflow diagram: {e}")
        except KeyboardInterrupt:
            logger.info("\n[Conductor] Interrupted! State is saved. Run again to resume.")
