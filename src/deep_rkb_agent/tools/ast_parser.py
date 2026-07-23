import os
import tree_sitter_python
import tree_sitter_java
import tree_sitter_go
from tree_sitter import Language, Parser

class ParserFactory:
    @staticmethod
    def get_parser(ext: str) -> tuple[Parser, str]:
        if ext == '.py':
            lang = Language(tree_sitter_python.language())
            parser = Parser(lang)
            return parser, 'python'
        elif ext == '.java':
            lang = Language(tree_sitter_java.language())
            parser = Parser(lang)
            return parser, 'java'
        elif ext == '.go':
            lang = Language(tree_sitter_go.language())
            parser = Parser(lang)
            return parser, 'go'
        else:
            raise ValueError(f"Unsupported extension: {ext}")

def extract_symbols(filepath: str) -> dict:
    """
    Parses a file and returns a dictionary containing its classes, 
    functions, and import statements, natively supporting multiple languages.
    """
    _, ext = os.path.splitext(filepath)
    
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            code = f.read()
    except Exception as e:
        return {"error": str(e)}
        
    try:
        parser, lang_type = ParserFactory.get_parser(ext)
    except ValueError as e:
        return {"error": str(e)}

    tree = parser.parse(bytes(code, "utf8"))
    
    classes = []
    functions = []
    imports = []
    
    def traverse(node):
        # Python
        if node.type == 'class_definition':
            name = ""
            for child in node.children:
                if child.type == 'identifier':
                    name = child.text.decode('utf8')
                    break
            if name: classes.append(name)
        elif node.type == 'function_definition':
            name = ""
            for child in node.children:
                if child.type == 'identifier':
                    name = child.text.decode('utf8')
                    break
            if name: functions.append(name)
        elif node.type in ('import_statement', 'import_from_statement'):
            imports.append(node.text.decode('utf8'))
            
        # Java
        elif node.type == 'class_declaration':
            name = ""
            for child in node.children:
                if child.type == 'identifier':
                    name = child.text.decode('utf8')
                    break
            if name: classes.append(name)
        elif node.type == 'method_declaration':
            name = ""
            for child in node.children:
                if child.type == 'identifier':
                    name = child.text.decode('utf8')
                    break
            if name: functions.append(name)
        elif node.type == 'import_declaration':
            imports.append(node.text.decode('utf8'))
            
        # Go
        elif node.type == 'type_declaration':
            # Go structs/interfaces
            for child in node.children:
                if child.type == 'type_spec':
                    for sub in child.children:
                        if sub.type == 'type_identifier':
                            classes.append(sub.text.decode('utf8'))
                            break
        elif node.type in ('function_declaration', 'method_declaration'):
            name = ""
            for child in node.children:
                if child.type in ('identifier', 'field_identifier'):
                    name = child.text.decode('utf8')
                    break
            if name: functions.append(name)
        elif node.type == 'import_spec':
            imports.append(node.text.decode('utf8'))

        for child in node.children:
            traverse(child)
            
    traverse(tree.root_node)
    
    return {
        "classes": classes,
        "functions": functions,
        "imports": imports
    }
