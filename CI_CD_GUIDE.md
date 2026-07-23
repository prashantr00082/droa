# CI/CD Integration Guide (Jenkins & Bitbucket)

This guide explains how to operate the Deep Repository Ontology Agent (DROA) in a standard enterprise CI/CD pipeline using Jenkins and Bitbucket.

## The Pipeline Lifecycle

The provided `Jenkinsfile` orchestrates the DROA execution. Here is how it functions:

1. **Trigger**: While it can be triggered automatically via a Bitbucket webhook on merge to `main`, if your organization uses manual triggers, developers can manually kick off the "Update Knowledge Base" Jenkins job after their primary build passes.
2. **Setup**: Jenkins provisions a virtual environment and installs requirements.
3. **Incremental Run**: Jenkins executes `python main.py .`. Because the `.rkb/state.db` file tracks the `sha256` hash of every file in the repo, DROA *instantly* skips files that haven't changed. Only the files modified in the PR are routed to the LLM (using the GLM 5.2 vs Qwen routing logic).
4. **Graph Export**: If configured, Jenkins can execute `cypher-shell` to push the generated `docs/load_graph.cypher` script directly to your Neo4j instance, keeping the GraphRAG live.
5. **Commit Back**: Finally, Jenkins commits the updated `.rkb/state.db` and the markdown documentation in `docs/` back to the Bitbucket repository (`git commit -m "... [skip ci]"`). This ensures the next run is incremental.

## Multi-Language Support (Java, Golang, etc.)

You asked: *"For java and golang repositories this will be mvn clean package and go build, will it still work?"*

**Current Status**: 
DROA is completely language-agnostic for the **Ontology Layer** (parsing directory structures, READMEs, and Entrypoints). 
However, the **Implementation Layer** (Module Documenter) currently utilizes Python's built-in `ast` module (`src/deep_rkb_agent/tools/ast_parser.py`) to parse symbols. Therefore, it currently only parses `.py` files.

**How to add Java/Golang Support**:
DROA does not need to run `mvn clean package` or `go build` to understand the code! It is a static analyzer. 
To support Java and Golang, you only need to do two things:
1. **Update the Scanner**: Modify `src/deep_rkb_agent/tools/scanner.py` to stop ignoring `.java` and `.go` extensions.
2. **Update the Parser**: Swap the `ast_parser.py` implementation to use **Tree-sitter** (which supports Java and Go natively). Once the Tree-sitter parser extracts the classes and functions, the JSON sidecars and the LLM prompts will work exactly identically across all languages!

No compilation is required for DROA to build its Knowledge Graph.
