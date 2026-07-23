import argparse
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))
from deep_rkb_agent.conductor import run_agent

def main():
    parser = argparse.ArgumentParser(description="Deep Repository Ontology Agent")
    parser.add_argument("repo_root", nargs="?", default=".", help="Path to the repository to process")
    parser.add_argument("--isolate", action="store_true", help="Run the agent in a new, isolated git branch")
    parser.add_argument("--org", default=None, help="Organization name for Enterprise Knowledge Graph")
    parser.add_argument("--subsystem", default=None, help="Subsystem name for Enterprise Knowledge Graph")
    parser.add_argument("--service", default=None, help="Service name for Enterprise Knowledge Graph")
    args = parser.parse_args()
    
    if not os.path.isdir(args.repo_root):
        print(f"Error: {args.repo_root} is not a directory.")
        return
        
    if args.isolate:
        import subprocess
        import time
        branch_name = f"droa-agent-run-{int(time.time())}"
        print(f"[Git Isolation] Creating and switching to new branch: {branch_name}")
        try:
            subprocess.run(["git", "checkout", "-b", branch_name], cwd=args.repo_root, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            print(f"[Git Isolation Error] Failed to create branch. Are you in a git repository?\n{e.stderr.decode()}")
            return
            
        print("[Git Isolation] Branch created. Starting agent...")
        run_agent(args.repo_root, org=args.org, subsystem=args.subsystem, service=args.service)
        
        print(f"[Git Isolation] Agent finished. Committing documentation to branch {branch_name}...")
        subprocess.run(["git", "add", "docs/", ".rkb/"], cwd=args.repo_root)
        subprocess.run(["git", "commit", "-m", f"DROA Automated Documentation Update"], cwd=args.repo_root)
        print(f"[Git Isolation] Success! Your main branch was unaffected. Review the docs on branch '{branch_name}'.")
    else:
        run_agent(args.repo_root, org=args.org, subsystem=args.subsystem, service=args.service)

if __name__ == "__main__":
    main()
