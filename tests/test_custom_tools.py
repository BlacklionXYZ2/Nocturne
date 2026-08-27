"""
Unit Test: Nocturne Dynamic Custom Tool Registration
====================================================
Verifies that custom tools written to `tools/custom/` are dynamically
discovered, validated, and registered into the ToolRegistry.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.base import registry


def test_custom_tool_registration():
    print("Testing Dynamic Custom Tool Loading...")
    
    custom_dir = Path("tools/custom")
    custom_dir.mkdir(parents=True, exist_ok=True)
    sample_tool_path = custom_dir / "math_sample.py"

    # Create a dynamic tool file
    sample_code = '''"""Sample dynamic tool."""
from tools.base import registry

@registry.register(name="calculate_sum", description="Adds two numbers together.")
def calculate_sum(a: int, b: int) -> str:
    return str(a + b)
'''
    sample_tool_path.write_text(sample_code, encoding="utf-8")

    # Load custom tools
    registry.load_custom_tools("tools/custom")

    assert "calculate_sum" in registry.tools, "Expected 'calculate_sum' to be in registry.tools"
    result = registry.execute("calculate_sum", {"a": 40, "b": 2})
    assert result == "42", f"Expected '42', got {result}"
    print(f"  [OK] Custom tool 'calculate_sum' executed dynamically: 40 + 2 = {result}")

    # Cleanup sample file
    if sample_tool_path.exists():
        sample_tool_path.unlink()


if __name__ == "__main__":
    test_custom_tool_registration()
    print("\n[SUCCESS] Dynamic custom tool test passed!")
