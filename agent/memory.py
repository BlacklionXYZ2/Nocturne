"""
Markdown File-Based Memory & Conversation Logger
=================================================
Implements an open, human-readable memory system that prevents context bloat:
1. Long-term memory is stored across modular Markdown files in `memory/`.
2. The agent reads and injects only curated sections of markdown into system prompts.
3. Every interactive session (Agent task or VTuber chat) is automatically archived to
   `conversations/YYYY-MM-DD_HH-MM-SS_[mode].md`.
"""

import os
import time
from typing import Dict, List, Any, Optional
from pathlib import Path


class MemoryManager:
    """Manages markdown-based persistent memory files and conversation history."""

    def __init__(self, memory_dir: str = "memory", conversations_dir: str = "conversations"):
        self.memory_dir = Path(memory_dir)
        self.conversations_dir = Path(conversations_dir)

        # Ensure storage directories exist
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.conversations_dir.mkdir(parents=True, exist_ok=True)

    # --------------------------------------------------------------------------
    # Markdown Memory File Management
    # --------------------------------------------------------------------------

    def list_memory_files(self) -> List[Dict[str, Any]]:
        """Lists all markdown files currently in the memory directory."""
        files = []
        for p in self.memory_dir.glob("*.md"):
            files.append({
                "filename": p.name,
                "path": str(p),
                "size_bytes": p.stat().st_size,
                "modified_time": time.ctime(p.stat().st_mtime)
            })
        return sorted(files, key=lambda x: x["filename"])

    def read_memory_file(self, filename: str) -> str:
        """Reads the content of a specific memory file."""
        file_path = self.memory_dir / filename
        if not file_path.is_file():
            return ""
        try:
            return file_path.read_text(encoding="utf-8")
        except Exception as e:
            return f"Error reading memory file {filename}: {e}"

    def read_memory(self, filename: str) -> str:
        """Alias for read_memory_file."""
        return self.read_memory_file(filename)

    def write_memory_file(self, filename: str, content: str) -> bool:
        """Writes or overwrites a memory file in the memory directory."""
        # Sanitize filename
        safe_name = Path(filename).name
        if not safe_name.endswith(".md"):
            safe_name += ".md"
        file_path = self.memory_dir / safe_name
        try:
            file_path.write_text(content, encoding="utf-8")
            return True
        except Exception as e:
            print(f"[MemoryManager] Error writing {safe_name}: {e}")
            return False

    def write_memory(self, filename: str, content: str) -> bool:
        """Alias for write_memory_file."""
        return self.write_memory_file(filename, content)

    def delete_memory_file(self, filename: str) -> bool:
        """Deletes a memory file."""
        file_path = self.memory_dir / Path(filename).name
        if file_path.is_file():
            try:
                file_path.unlink()
                return True
            except Exception as e:
                print(f"[MemoryManager] Error deleting {filename}: {e}")
                return False
        return False

    def get_combined_memory_prompt(self, mode: str = "agent") -> str:
        """
        Combines relevant memory files into a structured markdown block
        ready for injection into the system prompt.

        Args:
            mode: "agent" or "vtuber"
        """
        core = self.read_memory_file("core_knowledge.md")
        thoughts = self.read_memory_file("agent_thoughts.md")
        persona = self.read_memory_file("personality.md")

        sections = []

        if persona.strip():
            sections.append(f"### Persona, Voice & Mannerisms (Auri)\n{persona.strip()}")
        if core.strip():
            sections.append(f"### Core Environment & User Facts\n{core.strip()}")
        if thoughts.strip():
            sections.append(f"### Active Project Working Memory & Scratchpad\n{thoughts.strip()}")

        if not sections:
            return ""

        return (
            "\n\n=== LONG-TERM MEMORY (FILE-BASED) ===\n"
            "The following context is loaded from your persistent markdown memory files:\n\n"
            + "\n\n---\n\n".join(sections)
            + "\n=====================================\n"
        )

    # --------------------------------------------------------------------------
    # Conversation Archiving & Logging
    # --------------------------------------------------------------------------

    def create_session_logger(self, mode: str = "agent") -> "SessionLogger":
        """Spawns a session logger for an active conversation or task."""
        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"{timestamp}_{mode}.md"
        session_path = self.conversations_dir / filename
        return SessionLogger(session_path, mode)

    def list_conversations(self) -> List[Dict[str, Any]]:
        """Lists all saved conversation log files."""
        sessions = []
        for p in self.conversations_dir.glob("*.md"):
            sessions.append({
                "filename": p.name,
                "path": str(p),
                "size_bytes": p.stat().st_size,
                "modified_time": time.ctime(p.stat().st_mtime)
            })
        return sorted(sessions, key=lambda x: x["filename"], reverse=True)

    def list_conversation_logs(self) -> List[str]:
        """Returns filenames of past conversation logs."""
        return [f["filename"] for f in self.list_conversations()]

    def read_conversation(self, filename: str) -> str:
        """Reads a past conversation log file."""
        file_path = self.conversations_dir / Path(filename).name
        if file_path.is_file():
            return file_path.read_text(encoding="utf-8")
        return ""


class SessionLogger:
    """Records real-time turns, thoughts, tool executions, and responses to a markdown log file."""

    def __init__(self, log_path: Path, mode: str):
        self.log_path = log_path
        self.mode = mode
        self.header_written = False
        self._init_file()

    def _init_file(self):
        header = (
            f"# Session Log: {self.mode.upper()} Mode\n"
            f"- **Date**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"- **Log File**: `{self.log_path.name}`\n\n"
            f"---\n\n"
        )
        self.log_path.write_text(header, encoding="utf-8")
        self.header_written = True

    def log_turn(self, role: str, content: str, tool_calls: Optional[List[Dict[str, Any]]] = None, tool_results: Optional[List[Dict[str, Any]]] = None):
        """Appends a turn to the conversation log."""
        timestamp = time.strftime("%H:%M:%S")
        entry = [f"### [{timestamp}] {role.upper()}"]
        
        if content:
            entry.append(content)

        if tool_calls:
            entry.append("\n**Tool Executions:**")
            for tc in tool_calls:
                fn = tc.get("function", {})
                entry.append(f"```json\n// Tool: {fn.get('name')}\n{fn.get('arguments')}\n```")

        if tool_results:
            entry.append("\n**Tool Outputs:**")
            for tr in tool_results:
                entry.append(f"```text\n// Output from {tr.get('name')}:\n{tr.get('content')}\n```")

        entry.append("\n---\n")

        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write("\n".join(entry) + "\n")
