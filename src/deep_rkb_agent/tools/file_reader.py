import os

def read_file_window(filepath: str, start_line: int = 1, max_lines: int = 500) -> str:
    """
    Reads a window of lines from a file.
    Lines are 1-indexed.
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        return f"Error reading file {filepath}: {e}"
        
    total_lines = len(lines)
    
    # 0-indexed start
    start_idx = max(0, start_line - 1)
    end_idx = min(total_lines, start_idx + max_lines)
    
    window = lines[start_idx:end_idx]
    
    # Prefix each line with its line number to help LLM make accurate citations
    numbered_window = []
    for i, line in enumerate(window):
        line_num = start_idx + i + 1
        numbered_window.append(f"{line_num:4d} | {line}")
    
    header = f"--- FILE: {filepath} | LINES {start_idx+1}-{end_idx} of {total_lines} ---\n"
    content = "".join(numbered_window)
    footer = f"\n--- END OF WINDOW ---"
    
    return header + content + footer
