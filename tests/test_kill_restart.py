import os
import subprocess
import time
import sqlite3
import shutil
import sys

def run_test():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "fixtures/sample_repo"))
    rkb_dir = os.path.join(repo_root, ".rkb")
    docs_dir = os.path.join(repo_root, "docs")
    
    # Clean up from previous runs
    if os.path.exists(rkb_dir):
        shutil.rmtree(rkb_dir)
    if os.path.exists(docs_dir):
        shutil.rmtree(docs_dir)
        
    print("Starting agent...")
    main_py = os.path.abspath(os.path.join(os.path.dirname(__file__), "../main.py"))
    process = subprocess.Popen([sys.executable, main_py, repo_root])
    
    # Let it run for 8 seconds to ensure it gets past heavy imports and processes a few tasks
    time.sleep(8)
    
    print("\nSimulating kill (SIGINT)...")
    process.send_signal(subprocess.signal.SIGINT)
    process.wait()
    
    print("\nAgent killed. Checking state...")
    db_path = os.path.join(rkb_dir, "state.db")
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM tasks WHERE status='COMPLETE'")
        completed_before = cursor.fetchone()['count']
        cursor.execute("SELECT COUNT(*) as count FROM tasks")
        total_tasks = cursor.fetchone()['count']
        
    print(f"Tasks total: {total_tasks}, Completed before restart: {completed_before}")
    assert total_tasks == 5, f"Expected 5 tasks (3 global + 2 modules), got {total_tasks}"
    
    print("\nRestarting agent to completion...")
    subprocess.run([sys.executable, main_py, repo_root], check=True)
    
    print("\nAgent finished. Verifying final state...")
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM tasks WHERE status='COMPLETE'")
        completed_after = cursor.fetchone()['count']
        cursor.execute("SELECT COUNT(*) as count FROM tasks")
        total_tasks_after = cursor.fetchone()['count']
        
    print(f"Tasks total: {total_tasks_after}, Completed after restart: {completed_after}")
    assert total_tasks_after == 5, f"Expected 5 tasks, got {total_tasks_after} (duplication error!)"
    assert completed_after == 5, f"Expected all 5 tasks to be complete, got {completed_after}"
    
    print("\nTest passed! Kill and resume works correctly without duplicating tasks.")

if __name__ == "__main__":
    run_test()
