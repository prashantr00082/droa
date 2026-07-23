import sqlite3
import os
from typing import List, Dict, Any, Optional

def get_db_path(repo_root: str) -> str:
    return os.path.join(repo_root, ".rkb", "state.db")

def init_db(repo_root: str):
    os.makedirs(os.path.join(repo_root, ".rkb"), exist_ok=True)
    db_path = get_db_path(repo_root)
    
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                output TEXT NOT NULL,
                category TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'NOT_STARTED',
                priority INTEGER NOT NULL DEFAULT 1,
                confidence REAL,
                last_run TEXT,
                hash TEXT,
                notes TEXT,
                UNIQUE(source, category)
            )
        ''')
        
        # Reset any tasks that were left IN_PROGRESS due to a crash
        cursor.execute("UPDATE tasks SET status = 'NOT_STARTED' WHERE status = 'IN_PROGRESS'")
        conn.commit()

def add_tasks(repo_root: str, tasks: List[Dict[str, Any]]):
    db_path = get_db_path(repo_root)
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        for task in tasks:
            cursor.execute('''
                INSERT OR IGNORE INTO tasks (source, output, category, priority, hash)
                VALUES (?, ?, ?, ?, ?)
            ''', (task['source'], task['output'], task['category'], task.get('priority', 1), task.get('hash')))
        conn.commit()

def claim_next_task(repo_root: str) -> Optional[Dict[str, Any]]:
    db_path = get_db_path(repo_root)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Transaction block to avoid race conditions
        cursor.execute("BEGIN IMMEDIATE")
        try:
            cursor.execute('''
                SELECT id, source, output, category FROM tasks
                WHERE status = 'NOT_STARTED'
                ORDER BY priority DESC, id ASC
                LIMIT 1
            ''')
            row = cursor.fetchone()
            
            if row:
                cursor.execute("UPDATE tasks SET status = 'IN_PROGRESS' WHERE id = ?", (row['id'],))
                conn.commit()
                return dict(row)
            
            conn.commit()
            return None
        except Exception as e:
            conn.rollback()
            raise e

def claim_next_batch(repo_root: str, limit: int = 10) -> List[Dict[str, Any]]:
    db_path = get_db_path(repo_root)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Transaction block to avoid race conditions
        cursor.execute("BEGIN IMMEDIATE")
        try:
            cursor.execute(f'''
                SELECT id, source, output, category, priority FROM tasks
                WHERE status = 'NOT_STARTED'
                ORDER BY priority DESC, id ASC
                LIMIT {limit}
            ''')
            rows = cursor.fetchall()
            
            claimed = []
            if rows:
                ids = [r['id'] for r in rows]
                placeholders = ','.join(['?'] * len(ids))
                cursor.execute(f"UPDATE tasks SET status = 'IN_PROGRESS' WHERE id IN ({placeholders})", ids)
                conn.commit()
                claimed = [dict(r) for r in rows]
                return claimed
            
            conn.commit()
            return []
        except Exception as e:
            conn.rollback()
            raise e

def mark_task_complete(repo_root: str, task_id: int, confidence: float, new_hash: str = None):
    db_path = get_db_path(repo_root)
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE tasks 
            SET status = 'COMPLETE', confidence = ?, hash = ?, last_run = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (confidence, new_hash, task_id))
        conn.commit()

def requeue_task(repo_root: str, task_id: int):
    db_path = get_db_path(repo_root)
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE tasks 
            SET status = 'NOT_STARTED', priority = priority + 10 
            WHERE id = ?
        ''', (task_id,))
        conn.commit()

def export_progress(repo_root: str):
    db_path = get_db_path(repo_root)
    if not os.path.exists(db_path):
        return
        
    progress_file = os.path.join(repo_root, "docs", "repository-progress.md")
    os.makedirs(os.path.dirname(progress_file), exist_ok=True)
    
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM tasks ORDER BY id ASC')
        rows = cursor.fetchall()
        
        with open(progress_file, "w") as f:
            f.write("| ID | Source | Output | Category | Status | Priority | Confidence | LastRun | Hash | Notes |\n")
            f.write("|----|--------|--------|----------|--------|----------|-----------|---------|------|-------|\n")
            for row in rows:
                confidence = f"{row['confidence']:.2f}" if row['confidence'] is not None else "-"
                last_run = row['last_run'] if row['last_run'] else "-"
                hash_val = row['hash'] if row['hash'] else "-"
                notes = row['notes'] if row['notes'] else ""
                
                f.write(f"| {row['id']} | {row['source']} | {row['output']} | {row['category']} | {row['status']} | {row['priority']} | {confidence} | {last_run} | {hash_val} | {notes} |\n")
