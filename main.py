import argparse
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))
from deep_rkb_agent.conductor import run_agent

def main():
    parser = argparse.ArgumentParser(description="Deep Repository Ontology Agent")
    parser.add_argument("repo_root", nargs="?", default=".", help="Path to the repository to process")
    args = parser.parse_args()
    
    if not os.path.isdir(args.repo_root):
        print(f"Error: {args.repo_root} is not a directory.")
        return
        
    run_agent(args.repo_root)

if __name__ == "__main__":
    main()
