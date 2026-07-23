from pydantic import BaseModel, Field
from typing import List

class SymbolDoc(BaseModel):
    name: str = Field(description="Name of the class, function, or interface")
    type: str = Field(description="Type of the symbol: 'class', 'function', or 'interface'")
    responsibility: str = Field(description="One-sentence description of its purpose")
    collaborators: List[str] = Field(description="Other symbols in the same module it interacts with")
    depends_on: List[str] = Field(description="External modules or dependencies it calls")
    used_by: List[str] = Field(description="Modules that call this symbol (if known)")
    source_ref: str = Field(description="File and line number where defined, e.g. src/main.py:42")

class ModuleSidecar(BaseModel):
    module: str = Field(description="Fully qualified module name, e.g. deep_rkb_agent.conductor")
    source: str = Field(description="Path to the source file")
    confidence: float = Field(description="Agent's self-assessed confidence in the documentation (0.0 to 1.0)")
    symbols: List[SymbolDoc] = Field(description="Documented symbols (classes, functions, interfaces) in the module")
    external_deps: List[str] = Field(description="List of external packages or libraries this module imports")
    extension_points: List[str] = Field(description="Functions or classes designed to be subclassed or extended")
    config_keys: List[str] = Field(description="Configuration variables or environment variables read by this module")
    markdown_doc: str = Field(description="The full, human-readable markdown documentation for the module. YOU MUST ADD [file:line] citations for EVERY claim you make.")

# --- Ontology Schemas ---

class OntologyConcepts(BaseModel):
    markdown_doc: str = Field(description="The full ontology/concepts.md document. Must follow the required template with Domain Overview, Key Domain Concepts table, Key Technical Abstractions table, and Glossary. Every concept MUST cite evidence using [filename] notation.")

class OntologyRelationships(BaseModel):
    markdown_doc: str = Field(description="The full ontology/relationships.md document. Must include Dependency Summary, Module Dependency Table, Hub Modules, and Potential Concerns. Every claim MUST cite the import graph.")
    dependency_edges: List[dict] = Field(description="Machine-readable list of edges: [{from: 'module_a.py', to: 'module_b.py'}]")

class OntologyFlows(BaseModel):
    markdown_doc: str = Field(description="The full ontology/flows.md document including System Entrypoints, Primary Request Flow, Data Flow, and a Mermaid diagram. Every inference MUST cite a file.")

class OntologyOrganization(BaseModel):
    markdown_doc: str = Field(description="The full ontology/organization.md document including Ownership and Policy.")

# --- Synthesizer / Architecture Schemas ---

class ArchitectureComponents(BaseModel):
    markdown_doc: str = Field(description="The full architecture/components.md document, grouping modules into logical subsystems based on ontology.")

class ArchitectureDataModels(BaseModel):
    markdown_doc: str = Field(description="The full architecture/data-models.md document, aggregating Pydantic/SQLAlchemy models from module sidecars.")

class ArchitectureLessons(BaseModel):
    markdown_doc: str = Field(description="The full architecture/lessons_learned.md document, rolled up from the memory ledger.")

# --- Memory Schema ---

class AgentMemoryEntry(BaseModel):
    timestamp: str
    task_description: str
    architectural_decision: str
    rationale: str
    related_modules: List[str]
