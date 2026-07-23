import os
import json

def _escape_cypher(s: str) -> str:
    """Escapes strings for Cypher queries."""
    if not isinstance(s, str):
        return ""
    return s.replace('\\', '\\\\').replace('"', '\\"').replace("'", "\\'")

def export_to_cypher(repo_root: str, org: str = None, subsystem: str = None, service: str = None):
    """
    Reads all JSON sidecars and generates a load_graph.cypher script
    containing MERGE statements to populate a Neo4j knowledge graph.
    """
    print("  [Graph Exporter] Generating Neo4j Cypher script...")
    modules_dir = os.path.join(repo_root, "docs", "modules")
    
    sidecars = []
    if os.path.exists(modules_dir):
        for f in os.listdir(modules_dir):
            if f.endswith('.json'):
                try:
                    with open(os.path.join(modules_dir, f), 'r', encoding="utf-8") as fh:
                        sidecars.append(json.load(fh))
                except Exception:
                    pass

    model = None
    if os.environ.get("ENABLE_EMBEDDINGS", "false").lower() == "true":
        try:
            from sentence_transformers import SentenceTransformer
            print("  [Graph Exporter] Loading embedding model (all-MiniLM-L6-v2)...")
            model = SentenceTransformer('all-MiniLM-L6-v2')
        except ImportError:
            print("  [Graph Exporter] sentence_transformers not installed. Skipping vector embeddings.")
    else:
        print("  [Graph Exporter] Embeddings disabled by default (ENABLE_EMBEDDINGS!=true).")

    cypher_statements = []
    
    # 1. Create constraints (optional but good practice)
    cypher_statements.append("// Constraints")
    cypher_statements.append("CREATE CONSTRAINT module_path IF NOT EXISTS FOR (m:Module) REQUIRE m.path IS UNIQUE;")
    cypher_statements.append("CREATE CONSTRAINT symbol_id IF NOT EXISTS FOR (s:Symbol) REQUIRE s.id IS UNIQUE;\n")

    # 1.5. Enterprise Knowledge Layer (Hierarchy)
    cypher_statements.append("// Enterprise Knowledge Layer")
    if org:
        safe_org = _escape_cypher(org)
        cypher_statements.append(f'MERGE (o:Organization {{name: "{safe_org}"}});')
    if subsystem:
        safe_sub = _escape_cypher(subsystem)
        cypher_statements.append(f'MERGE (sub:Subsystem {{name: "{safe_sub}"}});')
        if org:
            cypher_statements.append(f'MATCH (o:Organization {{name: "{safe_org}"}}), (sub:Subsystem {{name: "{safe_sub}"}}) MERGE (o)-[:CONTAINS]->(sub);')
    if service:
        safe_srv = _escape_cypher(service)
        cypher_statements.append(f'MERGE (srv:Service {{name: "{safe_srv}"}});')
        if subsystem:
            cypher_statements.append(f'MATCH (sub:Subsystem {{name: "{safe_sub}"}}), (srv:Service {{name: "{safe_srv}"}}) MERGE (sub)-[:CONTAINS]->(srv);')
        elif org:
            cypher_statements.append(f'MATCH (o:Organization {{name: "{safe_org}"}}), (srv:Service {{name: "{safe_srv}"}}) MERGE (o)-[:CONTAINS]->(srv);')
    
    cypher_statements.append("")

    # 2. Modules
    cypher_statements.append("// Modules")
    for s in sidecars:
        path = _escape_cypher(s.get("source", ""))
        module_name = _escape_cypher(s.get("module", ""))
        confidence = s.get("confidence", 0.0)
        
        # Calculate embeddings if model is available
        embedding_str = ""
        if model is not None:
            doc_text = s.get("markdown_doc", "")
            if not doc_text:
                # Fallback to module name if no markdown text
                doc_text = module_name
            embedding = model.encode(doc_text).tolist()
            embedding_str = f", m.embedding = {embedding}"
            
        cypher_statements.append(
            f'MERGE (m:Module {{path: "{path}"}}) '
            f'SET m.name = "{module_name}", m.confidence = {confidence}{embedding_str};'
        )
        # Link Module to Service if available
        if service:
            safe_service = _escape_cypher(service)
            cypher_statements.append(
                f'MATCH (srv:Service {{name: "{safe_service}"}}), (m:Module {{path: "{path}"}}) '
                f'MERGE (srv)-[:CONTAINS]->(m);'
            )
    cypher_statements.append("")
    
    # 3. Symbols and CONTAINS edges
    cypher_statements.append("// Symbols & CONTAINS edges")
    for s in sidecars:
        module_path = _escape_cypher(s.get("source", ""))
        for sym in s.get("symbols", []):
            sym_name = _escape_cypher(sym.get("name", ""))
            sym_type = _escape_cypher(sym.get("type", ""))
            sym_resp = _escape_cypher(sym.get("responsibility", ""))
            sym_ref = _escape_cypher(sym.get("source_ref", ""))
            
            # Create a unique ID for the symbol based on its module and name
            sym_id = f"{module_path}::{sym_name}"
            
            cypher_statements.append(
                f'MERGE (s:Symbol {{id: "{sym_id}"}}) '
                f'SET s.name = "{sym_name}", s.type = "{sym_type}", '
                f's.responsibility = "{sym_resp}", s.source_ref = "{sym_ref}";'
            )
            # Create CONTAINS edge from Module to Symbol
            cypher_statements.append(
                f'MATCH (m:Module {{path: "{module_path}"}}), (s:Symbol {{id: "{sym_id}"}}) '
                f'MERGE (m)-[:CONTAINS]->(s);'
            )
    cypher_statements.append("")

    # 4. DEPENDS_ON edges (Symbol -> Module)
    # Our schema says depends_on contains a list of external modules/dependencies
    cypher_statements.append("// DEPENDS_ON edges")
    for s in sidecars:
        module_path = _escape_cypher(s.get("source", ""))
        for sym in s.get("symbols", []):
            sym_name = _escape_cypher(sym.get("name", ""))
            sym_id = f"{module_path}::{sym_name}"
            
            for dep in sym.get("depends_on", []):
                dep_path = _escape_cypher(dep)
                # Ensure the target module exists before creating the edge (in case it's an external library not in the graph)
                cypher_statements.append(
                    f'MATCH (s:Symbol {{id: "{sym_id}"}}), (m:Module {{path: "{dep_path}"}}) '
                    f'MERGE (s)-[:DEPENDS_ON]->(m);'
                )
    
    # 5. Write to file
    out_dir = os.path.join(repo_root, "docs")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "load_graph.cypher")
    
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(cypher_statements))
        
    print(f"  [Graph Exporter] Wrote {out_path}")
