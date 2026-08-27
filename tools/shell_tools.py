"""
PowerShell Shell Command Execution Tool with Safety Guardrails
==============================================================
Enables the autonomous agent to run shell commands, inspect system state,
execute scripts, or compile code using Windows PowerShell with safety guardrails.
"""

import sys
import re
import subprocess
from typing import Optional
from pathlib import Path

from .base import registry

# Blocklist of catastrophic system/destructive commands
BLOCKED_PATTERNS = [
    r"format-volume",
    r"diskpart",
    r"remove-item\s+.*[cC]:\\(windows|system32)",
    r"rmdir\s+/s\s+/q\s+[cC]:\\(windows|system32)",
    r"del\s+/s\s+/q\s+[cC]:\\(windows|system32)",
    r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;",  # Fork bomb
    r"shutdown\s+/[srf]",
    r"bcdedit",
    r"reg\s+delete\s+hklm",
]


def _check_command_safety(command: str) -> Optional[str]:
    """Checks if a command contains dangerous destructive patterns."""
    cmd_lower = command.lower()
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, cmd_lower):
            return f"Security Refusal: Command matched dangerous pattern '{pattern}'. Execution blocked by Nocturne safety guard."
    return None


@registry.register(
    name="run_powershell_command",
    description="Executes a PowerShell command on the Windows system and returns stdout and stderr. Includes timeout and safety guards."
)
def run_powershell_command(command: str, timeout_seconds: int = 60, working_dir: Optional[str] = None) -> str:
    """
    Runs a command via PowerShell with timeout protection, safety guardrails, and output capture.

    Args:
        command: The PowerShell command string to execute.
        timeout_seconds: Maximum seconds before killing the process.
        working_dir: Directory in which to run the command (defaults to current dir).

    Returns:
        Formatted string containing exit code, stdout, and stderr.
    """
    # Safety Check
    security_error = _check_command_safety(command)
    if security_error:
        return security_error

    try:
        ps_executable = "powershell.exe"
        cmd = [ps_executable, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", command]

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=working_dir,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )

        try:
            stdout, stderr = process.communicate(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            process.kill()
            return f"Error: Command timed out after {timeout_seconds} seconds."

        output = []
        output.append(f"Exit Code: {process.returncode}")

        if stdout.strip():
            clean_out = stdout.strip()
            if len(clean_out) > 3000:
                clean_out = clean_out[:3000] + "\n... [Output truncated to 3000 characters]"
            output.append(f"Stdout:\n{clean_out}")

        if stderr.strip():
            clean_err = stderr.strip()
            if len(clean_err) > 1500:
                clean_err = clean_err[:1500] + "\n... [Stderr truncated]"
            output.append(f"Stderr:\n{clean_err}")

        if not stdout.strip() and not stderr.strip():
            output.append("(No output returned)")

        return "\n".join(output)

    except Exception as e:
        return f"Execution Error: {type(e).__name__} - {str(e)}"
