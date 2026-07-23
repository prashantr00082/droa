import os
import sys
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from deep_rkb_agent.tools.import_graph import (
    build_import_graph,
    build_tree_summary,
    find_readmes,
    find_entrypoints
)

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "fixtures/sample_repo"))

def test_import_graph():
    graph = build_import_graph(REPO)
    print("Import graph:")
    print(json.dumps(graph, indent=2))
    # sample_repo/main.py should be in the graph
    assert any("main.py" in k for k in graph), "main.py should be in the import graph"
    assert any("utils.py" in k for k in graph), "utils.py should be in the import graph"
    print("  PASS: import graph contains expected files\n")

def test_tree_summary():
    tree = build_tree_summary(REPO)
    print("Tree summary:")
    print(tree)
    assert "main.py" in tree
    assert "utils.py" in tree
    print("  PASS: tree contains expected files\n")

def test_readmes():
    readme = find_readmes(REPO)
    print(f"README content: {repr(readme[:80])}")
    # It's ok if there's no README, just make sure it doesn't crash
    print("  PASS: find_readmes did not crash\n")

def test_entrypoints():
    eps = find_entrypoints(REPO)
    print("Entrypoints:")
    print(json.dumps(eps, indent=2))
    # main.py has `if __name__ == "__main__"` and is named main.py
    names = [e["path"] for e in eps]
    assert any("main.py" in n for n in names), f"main.py should be an entrypoint, got: {names}"
    print("  PASS: entrypoints detected correctly\n")

if __name__ == "__main__":
    test_import_graph()
    test_tree_summary()
    test_readmes()
    test_entrypoints()
    print("All Cartographer tool tests passed!")
