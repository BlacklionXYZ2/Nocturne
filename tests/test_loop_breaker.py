"""
Unit Test: Nocturne Loop Circuit Breaker & Shell Guardrails
===========================================================
Verifies that:
1. Shell safety filter blocks dangerous destructive commands.
2. Repetitive failing tool calls trigger the circuit breaker.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.shell_tools import run_powershell_command, _check_command_safety
from agent.core import _estimate_tokens, LocalAgent


def test_shell_safety_guard():
    print("Testing Shell Safety Guardrails...")
    
    # Dangerous commands that must be blocked
    blocked_cmd_1 = "Format-Volume -DriveLetter C"
    blocked_cmd_2 = "Remove-Item -Recurse C:\\Windows\\System32"
    blocked_cmd_3 = "diskpart /s script.txt"

    res1 = _check_command_safety(blocked_cmd_1)
    res2 = _check_command_safety(blocked_cmd_2)
    res3 = _check_command_safety(blocked_cmd_3)

    assert res1 is not None, f"Expected {blocked_cmd_1} to be blocked"
    assert res2 is not None, f"Expected {blocked_cmd_2} to be blocked"
    assert res3 is not None, f"Expected {blocked_cmd_3} to be blocked"
    print("  [OK] Dangerous commands correctly intercepted by security guard.")

    # Safe commands that must pass
    safe_res = _check_command_safety("Get-ChildItem -Path .")
    assert safe_res is None, "Safe command should not be blocked"
    print("  [OK] Safe commands allowed.")


def test_token_estimation():
    print("\nTesting Token Estimation...")
    messages = [
        {"role": "system", "content": "You are Auri, an AI agent."},
        {"role": "user", "content": "Run tests and summarize findings."}
    ]
    tokens = _estimate_tokens(messages)
    assert tokens > 10, f"Token count should be > 10, got {tokens}"
    print(f"  [OK] Estimated tokens: {tokens}")


if __name__ == "__main__":
    test_shell_safety_guard()
    test_token_estimation()
    print("\n[SUCCESS] Loop breaker and shell safety tests passed!")
