import asyncio
import sys
from pathlib import Path

root_dir = Path('.').resolve()
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import httpx
from server.app import app, llama_mgr
from backend.model_scanner import ModelScanner

async def test_start_endpoint():
    scanner = ModelScanner(r"C:\Users\oscar\Desktop\Models")
    models = scanner.scan()
    # Pick a smaller model for fast test first: gemma-4-E4B-it-Q4_K_M.gguf (4.6GB)
    small_model = next((m for m in models if "e4b" in m["name"].lower()), models[0])
    print(f"[TEST] Testing /api/server/start with: {small_model['name']} ({small_model['size_gb']} GB)")

    payload = {
        "model": small_model["full_path"],
        "params": {
            "ctx_size": 4096,
            "n_gpu_layers": 99,
            "device": "ROCm0",
            "flash_attn": True,
            "cache_type_k": "q8_0",
            "cache_type_v": "q8_0"
        }
    }

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", timeout=60.0) as client:
        print("[TEST] Sending POST /api/server/start...")
        res = await client.post("/api/server/start", json=payload)
        print(f"[TEST] Status Code: {res.status_code}")
        print(f"[TEST] Response: {res.text}")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"

    print("[TEST] Checking if llama_mgr is running...")
    print(f"  is_running: {llama_mgr.is_running}")
    print(f"  power_state: {llama_mgr.power_state}")
    print(f"  base_url: {llama_mgr.base_url}")
    
    print("[TEST] Stopping llama_mgr...")
    llama_mgr.stop()
    print("[TEST] Successfully stopped.")

if __name__ == "__main__":
    asyncio.run(test_start_endpoint())
