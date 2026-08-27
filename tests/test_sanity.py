"""
Sanity check script to test all Local Agent modules
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.model_scanner import ModelScanner
from agent.memory import MemoryManager
from tools.base import registry
from backend.params import LlamaServerParams

def test_all():
    print("--- 1. Testing ModelScanner ---")
    scanner = ModelScanner(r"C:\Users\oscar\Desktop\Models")
    models = scanner.scan()
    print(f"Discovered {len(models)} GGUF models:")
    for m in models:
        print(f"  - {m['name']} ({m['size_gb']} GB, Quant: {m['quantization']}, Role: {m['recommended_role']})")

    print("\n--- 2. Testing MemoryManager ---")
    mem = MemoryManager("memory", "conversations")
    files = mem.list_memory_files()
    print(f"Discovered {len(files)} memory files:")
    for f in files:
        print(f"  - {f['filename']} ({f['size_bytes']} bytes)")

    prompt = mem.get_combined_memory_prompt("agent")
    print(f"Agent memory prompt preview ({len(prompt)} chars):\n{prompt[:250]}...")

    print("\n--- 3. Testing ToolRegistry ---")
    tools = registry.get_openai_tools()
    print(f"Registered {len(tools)} tools:")
    for t in tools:
        print(f"  - {t['function']['name']}: {t['function']['description']}")

    print("\n--- 4. Testing LlamaServerParams ---")
    params = LlamaServerParams(
        ctx_size=16384,
        n_gpu_layers=99,
        device="ROCm0",
        flash_attn=True,
        cache_type_k="q8_0",
        cache_type_v="q8_0"
    )
    cli_args = params.build_cli_args("C:\\Users\\oscar\\Desktop\\Models\\Unsloth\\gemma-4-E4B-it-Q4_K_M.gguf")
    print("Compiled CLI flags:")
    print(" ", " ".join(cli_args))
    print("\n[SUCCESS] All component sanity checks passed!")

if __name__ == "__main__":
    test_all()
