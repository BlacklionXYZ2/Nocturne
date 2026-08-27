"""
Test VRAM and ideal environment calculator
"""

import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from backend.model_scanner import read_gguf_header_metadata
import glob

def _to_int(val, default=1):
    if val is None:
        return default
    if isinstance(val, (list, tuple)):
        return int(val[0]) if val else default
    if isinstance(val, int):
        return val
    try:
        return int(val)
    except Exception:
        return default

def compute_ideal_profile(filepath):
    p = Path(filepath)
    meta = read_gguf_header_metadata(p)
    if not meta: return None

    arch = meta.get("general.architecture", "generic")
    size_gb = round(p.stat().st_size / (1024**3), 2)

    block_count = _to_int(meta.get(f"{arch}.block_count") or meta.get("llama.block_count"), 32)
    head_count = _to_int(meta.get(f"{arch}.attention.head_count") or meta.get("llama.attention.head_count"), 32)
    head_count_kv = _to_int(meta.get(f"{arch}.attention.head_count_kv") or meta.get("llama.attention.head_count_kv"), head_count)
    embed_len = _to_int(meta.get(f"{arch}.embedding_length") or meta.get("llama.embedding_length"), 4096)
    max_ctx = _to_int(meta.get(f"{arch}.context_length") or meta.get("llama.context_length"), 32768)
    expert_count = _to_int(meta.get(f"{arch}.expert_count") or meta.get("llama.expert_count"), 0)
    expert_used = _to_int(meta.get(f"{arch}.expert_used_count") or meta.get("llama.expert_used_count"), 0)

    head_dim = embed_len // head_count if head_count else 128

    # Bytes per token for KV cache
    bytes_per_token_f16 = 2 * block_count * head_count_kv * head_dim * 2
    bytes_per_token_q8  = 2 * block_count * head_count_kv * head_dim * 1
    bytes_per_token_q4  = int(2 * block_count * head_count_kv * head_dim * 0.5)

    # VRAM calculation at 32k context with q8_0
    kv_32k_mb_q8 = (bytes_per_token_q8 * 32768) / (1024**2)
    total_vram_32k = size_gb + (kv_32k_mb_q8 / 1024) + 0.6  # 600MB CUDA/ROCm graph overhead

    # Optimal recommended context within 15.5 GB available VRAM on RX 9070 XT
    vram_budget_for_kv = max(0.5, 15.5 - size_gb - 0.6) * (1024**3)
    max_safe_ctx_q8 = int(vram_budget_for_kv // max(1, bytes_per_token_q8))
    # Round down to nearest 4096 and cap at max_ctx
    ideal_ctx = min(max_ctx, max(8192, (max_safe_ctx_q8 // 4096) * 4096))

    return {
        "name": p.name,
        "arch": arch,
        "size_gb": size_gb,
        "block_count": block_count,
        "gqa_ratio": f"{head_count}:{head_count_kv}",
        "moe": f"{expert_count} experts ({expert_used} active)" if expert_count else "Dense",
        "max_native_ctx": max_ctx,
        "kv_per_32k_q8_mb": round(kv_32k_mb_q8, 1),
        "total_vram_at_32k_gb": round(total_vram_32k, 2),
        "ideal_gpu_ctx_16gb": ideal_ctx,
        "recommended_kv_quant": "q8_0" if ideal_ctx >= 32768 else "f16"
    }

def main():
    for p in glob.glob(r"C:\Users\oscar\Desktop\Models\**\*.gguf", recursive=True):
        if "dflash" in p.lower() or "mtp" in p.lower(): continue
        prof = compute_ideal_profile(p)
        if prof:
            print(f"=== {prof['name']} ===")
            print(f"  Architecture: {prof['arch']} | MoE: {prof['moe']}")
            print(f"  Layers: {prof['block_count']} | GQA Heads: {prof['gqa_ratio']}")
            print(f"  Weight Size: {prof['size_gb']} GB | Native Max Ctx: {prof['max_native_ctx']:,} tokens")
            print(f"  KV Cache @ 32k (q8_0): {prof['kv_per_32k_q8_mb']} MB")
            print(f"  -> Ideal Max Context for 16GB VRAM: {prof['ideal_gpu_ctx_16gb']:,} tokens (KV: {prof['recommended_kv_quant']})")
            print()

if __name__ == "__main__":
    main()
