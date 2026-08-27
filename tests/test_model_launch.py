import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from backend.llama_manager import LlamaServerManager
from backend.model_scanner import ModelScanner
from backend.params import LlamaServerParams

def test_launch():
    scanner = ModelScanner(r"C:\Users\oscar\Desktop\Models")
    models = scanner.scan()
    if not models:
        print("No models found!")
        return

    m = models[0]
    print(f"Testing launch of: {m['name']} ({m['full_path']})")
    
    mgr = LlamaServerManager(llama_server_path=r"C:\llama.cpp\llama-server.exe", host="127.0.0.1", port=8080)
    params = LlamaServerParams(
        ctx_size=8192,
        n_gpu_layers=99,
        device="ROCm0",
        flash_attn=True,
        cache_type_k="q8_0",
        cache_type_v="q8_0"
    )

    args = params.build_cli_args(m['full_path'], host="127.0.0.1", port=8080)
    print(f"Built CLI args: {args}")
    
    success = mgr.start(m['full_path'], params=params, timeout_seconds=15)
    print(f"Start success: {success}")
    print("Logs:")
    for l in mgr.logs:
        print(f"  {l}")
    
    if success:
        print("Server is responding! Stopping server now...")
        mgr.stop()
        print("Server stopped cleanly.")

if __name__ == "__main__":
    test_launch()
