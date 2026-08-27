"""
Tool Registry & Schema Generator
=================================
Provides a decorator-based tool registry that automatically converts Python functions
and docstrings into OpenAI-compatible JSON tool schemas for `llama-server`.
"""

import inspect
from typing import Callable, Dict, Any, List, Optional
from pydantic import BaseModel


class Tool:
    """Represents an executable local agent tool."""

    def __init__(self, name: str, description: str, func: Callable, parameters_schema: Dict[str, Any]):
        self.name = name
        self.description = description
        self.func = func
        self.parameters_schema = parameters_schema

    def to_openai_tool_schema(self) -> Dict[str, Any]:
        """Formats the tool into the OpenAI JSON schema required by llama.cpp."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema
            }
        }

    def execute(self, **kwargs) -> str:
        """Invokes the underlying python function with error trapping."""
        try:
            result = self.func(**kwargs)
            return str(result)
        except Exception as e:
            return f"Error executing tool '{self.name}': {type(e).__name__} - {str(e)}"


class ToolRegistry:
    """Registry maintaining active agent tools."""

    def __init__(self):
        self.tools: Dict[str, Tool] = {}

    def register(self, name: Optional[str] = None, description: Optional[str] = None):
        """
        Decorator to register a python function as an Agent Tool.

        Example:
            @registry.register(name="read_file", description="Reads text from a file")
            def read_file(file_path: str) -> str:
                ...
        """
        def decorator(func: Callable):
            tool_name = name or func.__name__
            tool_desc = description or (func.__doc__.strip() if func.__doc__ else f"Tool {tool_name}")
            
            # Generate JSON Schema parameters from function signature
            sig = inspect.signature(func)
            properties: Dict[str, Any] = {}
            required: List[str] = []

            for param_name, param in sig.parameters.items():
                param_type = "string"
                if param.annotation == int:
                    param_type = "integer"
                elif param.annotation == float:
                    param_type = "number"
                elif param.annotation == bool:
                    param_type = "boolean"
                elif param.annotation == list or param.annotation == List[str]:
                    param_type = "array"

                properties[param_name] = {
                    "type": param_type,
                    "description": f"Parameter: {param_name}"
                }

                if param.default == inspect.Parameter.empty:
                    required.append(param_name)

            schema = {
                "type": "object",
                "properties": properties,
                "required": required
            }

            tool_obj = Tool(tool_name, tool_desc, func, schema)
            self.tools[tool_name] = tool_obj
            return func

        return decorator

    def get_openai_tools(self) -> List[Dict[str, Any]]:
        """Returns the list of all registered tools formatted for OpenAI API."""
        return [tool.to_openai_tool_schema() for tool in self.tools.values()]

    def execute(self, name: str, arguments: Dict[str, Any]) -> str:
        """Executes a registered tool by name with arguments."""
        # Refresh custom tools before execution if new tools were added
        self.load_custom_tools()
        if name not in self.tools:
            return f"Error: Tool '{name}' is not recognized. Available tools: {list(self.tools.keys())}"
        return self.tools[name].execute(**arguments)

    def load_custom_tools(self, custom_dir: str = "tools/custom"):
        """Dynamically scans and imports custom tools written by Auri or the user."""
        import os
        import importlib.util
        from pathlib import Path

        p = Path(custom_dir)
        p.mkdir(parents=True, exist_ok=True)

        for file in p.glob("*.py"):
            if file.name.startswith("_"):
                continue
            module_name = f"tools.custom.{file.stem}"
            try:
                spec = importlib.util.spec_from_file_location(module_name, str(file))
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
            except Exception as e:
                print(f"[Nocturne Tools] Error importing custom tool {file.name}: {e}", flush=True)


# Global Default Registry
registry = ToolRegistry()

