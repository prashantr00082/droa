import os
import sys
import json
import shutil

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
from deep_rkb_agent.agents.graph_exporter import export_to_cypher

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "fixtures/sample_repo"))

def test_graph_exporter():
    # Setup mock JSON sidecars
    docs_dir = os.path.join(REPO, "docs")
    modules_dir = os.path.join(docs_dir, "modules")
    
    os.makedirs(modules_dir, exist_ok=True)
    
    mock_data = {
        "source": "src/core/agent.py",
        "module": "AgentCore",
        "confidence": 0.95,
        "symbols": [
            {
                "name": "run_agent",
                "type": "function",
                "responsibility": "Orchestrates the workflow",
                "source_ref": "L10-L20",
                "depends_on": ["src/core/db.py"]
            }
        ]
    }
    
    with open(os.path.join(modules_dir, "agent.json"), "w") as f:
        json.dump(mock_data, f)
        
    mock_dep = {
        "source": "src/core/db.py",
        "module": "Database",
        "confidence": 0.99,
        "symbols": []
    }
    
    with open(os.path.join(modules_dir, "db.json"), "w") as f:
        json.dump(mock_dep, f)
        
    # Run exporter
    export_to_cypher(REPO)
    
    # Validate report
    cypher_path = os.path.join(docs_dir, "load_graph.cypher")
    assert os.path.exists(cypher_path)
    
    with open(cypher_path, "r") as f:
        content = f.read()
        
    print("Cypher Output:")
    print(content)
    
    # Assertions
    assert 'MERGE (m:Module {path: "src/core/agent.py"})' in content
    assert 'SET m.name = "AgentCore", m.confidence = 0.95' in content
    assert 'MERGE (s:Symbol {id: "src/core/agent.py::run_agent"})' in content
    assert 'MERGE (m)-[:CONTAINS]->(s)' in content
    assert 'MATCH (s:Symbol {id: "src/core/agent.py::run_agent"}), (m:Module {path: "src/core/db.py"})' in content
    assert 'MERGE (s)-[:DEPENDS_ON]->(m)' in content
    
    # Clean up mock files
    shutil.rmtree(docs_dir)
    print("  PASS: Cypher exporter correctly generated MERGE statements\n")

if __name__ == "__main__":
    test_graph_exporter()
    print("All Graph Exporter tests passed!")
