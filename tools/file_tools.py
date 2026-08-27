"""
Local File System Tools
========================
Provides safe, local file operations: reading, writing, snippet editing,
listing directories, and searching for files.
"""

import os
import glob
from pathlib import Path
from typing import List, Optional

from .base import registry


@registry.register(
    name="read_file",
    description="Reads the text content of a file from disk. Provide an absolute or relative path."
)
def read_file(path: str, max_lines: int = 500) -> str:
    """Reads a file and returns its content with line numbers."""
    target = Path(path)
    if not target.is_file():
        return f"Error: File does not exist at '{path}'."

    try:
        lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
        total_lines = len(lines)
        truncated = lines[:max_lines]
        
        output = [f"--- File: {target.name} ({total_lines} total lines) ---"]
        for i, line in enumerate(truncated, start=1):
            output.append(f"{i:4d} | {line}")
            
        if total_lines > max_lines:
            output.append(f"... Truncated: showing first {max_lines} of {total_lines} lines.")
            
        return "\n".join(output)
    except Exception as e:
        return f"Error reading file '{path}': {e}"


@registry.register(
    name="write_file",
    description="Creates a new file or completely overwrites an existing file with the provided content."
)
def write_file(path: str, content: str) -> str:
    """Writes content to a file, creating parent directories if necessary."""
    target = Path(path)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"Successfully wrote {len(content)} characters to '{target.resolve()}'."
    except Exception as e:
        return f"Error writing to file '{path}': {e}"


@registry.register(
    name="edit_file_snippet",
    description="Replaces an exact snippet of text in an existing file with new replacement text."
)
def edit_file_snippet(path: str, target_snippet: str, replacement_snippet: str) -> str:
    """Performs an exact string replacement in a file."""
    target = Path(path)
    if not target.is_file():
        return f"Error: File does not exist at '{path}'."

    try:
        content = target.read_text(encoding="utf-8")
        if target_snippet not in content:
            return f"Error: The target snippet was not found in '{path}'. Please check exact spacing and lines."
        
        occurrences = content.count(target_snippet)
        if occurrences > 1:
            return f"Error: The target snippet appears {occurrences} times. Provide more surrounding context to match uniquely."

        new_content = content.replace(target_snippet, replacement_snippet, 1)
        target.write_text(new_content, encoding="utf-8")
        return f"Successfully updated '{path}'."
    except Exception as e:
        return f"Error editing file '{path}': {e}"


@registry.register(
    name="list_directory",
    description="Lists the files and subdirectories inside a given directory path."
)
def list_directory(directory_path: str = ".") -> str:
    """Lists files and folders in the target directory."""
    target = Path(directory_path)
    if not target.is_dir():
        return f"Error: Directory does not exist at '{directory_path}'."

    try:
        items = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        output = [f"Contents of '{target.resolve()}':"]
        for item in items:
            prefix = "[DIR] " if item.is_dir() else "[FILE]"
            size = f"({round(item.stat().st_size / 1024, 1)} KB)" if item.is_file() else ""
            output.append(f"  {prefix} {item.name} {size}")
        return "\n".join(output)
    except Exception as e:
        return f"Error listing directory '{directory_path}': {e}"


@registry.register(
    name="search_files",
    description="Searches for files matching a glob pattern (e.g. '*.py' or '**/*.gguf') within a root directory."
)
def search_files(directory_path: str = ".", pattern: str = "*") -> str:
    """Recursively searches for matching files."""
    root = Path(directory_path)
    if not root.is_dir():
        return f"Error: Directory does not exist at '{directory_path}'."

    try:
        matches = list(root.glob(pattern))[:50]
        if not matches:
            return f"No files matched pattern '{pattern}' in '{directory_path}'."

        output = [f"Found {len(matches)} matching items for '{pattern}':"]
        for match in matches:
            prefix = "[DIR] " if match.is_dir() else "[FILE]"
            output.append(f"  {prefix} {match.relative_to(root)}")
        return "\n".join(output)
    except Exception as e:
        return f"Error searching files: {e}"
