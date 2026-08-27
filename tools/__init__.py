"""
Local Agent Tools Package
==========================
Exposes registry and initializes all default local tools (file, shell, web, Moltbook, 1F916).
"""

from .base import registry, Tool, ToolRegistry
from . import file_tools
from . import shell_tools
from . import web_tools
from . import moltbook_tools
from . import onef916_tools

__all__ = ["registry", "Tool", "ToolRegistry"]
