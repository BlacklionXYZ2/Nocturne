"""
Verify model scanner filtering and new tools
"""

import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from backend.model_scanner import ModelScanner
from tools.base import registry

def test_updates():
    scanner = ModelScanner(r"C:\Users\oscar\Desktop\Models")
    models = scanner.scan()
    print(f"Primary models discovered: {len(models)}")
    for m in models:
        draft_info = ""
        if m.get("companion_draft_model"):
            draft_info = f" [Draft: {m['companion_draft_model']['filename']}]"
        print(f"  - {m['name']} ({m['size_gb']} GB, Quant: {m['quantization']}){draft_info}")

    tools = registry.get_openai_tools()
    print(f"\nTotal registered tools: {len(tools)}")
    for t in tools:
        print(f"  - {t['function']['name']}: {t['function']['description'][:60]}...")

if __name__ == "__main__":
    test_updates()
