"""
GGUF Model Scanner & Hardware Architecture Profiler
===================================================
Reads GGUF binary headers directly and calculates the optimal hardware execution
environment (VRAM footprint, GQA KV cache scaling, ideal context length, and sampling)
tailored for the user's AMD Radeon RX 9070 XT (16 GB VRAM).
"""

import os
import struct
import re
from typing import List, Dict, Any, Optional
from pathlib import Path


def _to_int(val: Any, default: int = 1) -> int:
    """Helper to safely parse integer or sequence from GGUF metadata."""
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


def read_gguf_header_metadata(filepath: Path) -> Dict[str, Any]:
    """
    Parses the GGUF binary header without reading tensor weights (< 2ms).
    """
    meta: Dict[str, Any] = {}
    try:
        with open(filepath, 'rb') as f:
            magic = f.read(4)
            if magic != b'GGUF':
                return meta
            version = struct.unpack('<I', f.read(4))[0]
            tensor_count = struct.unpack('<Q', f.read(8))[0]
            kv_count = struct.unpack('<Q', f.read(8))[0]

            for _ in range(kv_count):
                klen_bytes = f.read(8)
                if len(klen_bytes) < 8:
                    break
                klen = struct.unpack('<Q', klen_bytes)[0]
                key = f.read(klen).decode('utf-8', errors='replace')
                vtype = struct.unpack('<I', f.read(4))[0]

                if vtype == 0: val = struct.unpack('<B', f.read(1))[0]
                elif vtype == 1: val = struct.unpack('<b', f.read(1))[0]
                elif vtype == 2: val = struct.unpack('<H', f.read(2))[0]
                elif vtype == 3: val = struct.unpack('<h', f.read(2))[0]
                elif vtype == 4: val = struct.unpack('<I', f.read(4))[0]
                elif vtype == 5: val = struct.unpack('<i', f.read(4))[0]
                elif vtype == 6: val = struct.unpack('<f', f.read(4))[0]
                elif vtype == 7: val = struct.unpack('<?', f.read(1))[0]
                elif vtype == 8:
                    slen = struct.unpack('<Q', f.read(8))[0]
                    val = f.read(slen).decode('utf-8', errors='replace')
                elif vtype == 9:
                    atype = struct.unpack('<I', f.read(4))[0]
                    alen = struct.unpack('<Q', f.read(8))[0]
                    if atype == 8:
                        for _ in range(alen):
                            slen = struct.unpack('<Q', f.read(8))[0]
                            f.seek(slen, 1)
                    else:
                        sizes = {0:1, 1:1, 2:2, 3:2, 4:4, 5:4, 6:4, 7:1, 10:8, 11:8, 12:8}
                        f.seek(alen * sizes.get(atype, 1), 1)
                    val = f"<array len={alen}>"
                elif vtype == 10: val = struct.unpack('<Q', f.read(8))[0]
                elif vtype == 11: val = struct.unpack('<q', f.read(8))[0]
                elif vtype == 12: val = struct.unpack('<d', f.read(8))[0]
                else:
                    break
                meta[key] = val
    except Exception as e:
        print(f"[GGUFReader] Header warning on {filepath.name}: {e}")
    return meta


class ModelInfo:
    """Represents a discovered model with architectural metadata and VRAM profile."""

    def __init__(self, full_path: Path, base_dir: Path):
        self.full_path = full_path
        self.filename = full_path.name
        self.relative_path = str(full_path.relative_to(base_dir)).replace("\\", "/")
        self.size_bytes = full_path.stat().st_size
        self.size_gb = round(self.size_bytes / (1024 ** 3), 2)
        
        # Read exact metadata directly from GGUF binary header
        raw_meta = read_gguf_header_metadata(full_path)
        
        self.architecture = str(raw_meta.get("general.architecture", "generic"))
        self.quantization = self._detect_quantization()
        self.recommended_role = self._classify_role()
        
        # Architectural dimensions
        arch = self.architecture
        self.block_count = _to_int(raw_meta.get(f"{arch}.block_count") or raw_meta.get("llama.block_count"), 32)
        self.head_count = _to_int(raw_meta.get(f"{arch}.attention.head_count") or raw_meta.get("llama.attention.head_count"), 32)
        self.head_count_kv = _to_int(raw_meta.get(f"{arch}.attention.head_count_kv") or raw_meta.get("llama.attention.head_count_kv"), self.head_count)
        self.embedding_length = _to_int(raw_meta.get(f"{arch}.embedding_length") or raw_meta.get("llama.embedding_length"), 4096)
        self.max_context_length = self._extract_max_context_length(raw_meta)
        
        # MoE structure
        expert_count = _to_int(raw_meta.get(f"{arch}.expert_count") or raw_meta.get("llama.expert_count"), 0)
        expert_used = _to_int(raw_meta.get(f"{arch}.expert_used_count") or raw_meta.get("llama.expert_used_count"), 0)
        self.moe_info = f"{expert_count} experts ({expert_used} active)" if expert_count else "Dense"

        # KV Cache memory scaling calculation (accounting for Sliding Window Attention in Gemma/Mistral)
        head_dim = self.embedding_length // self.head_count if self.head_count else 128
        swa_factor = 0.25 if "gemma" in arch.lower() else (0.5 if "mistral" in arch.lower() else 1.0)
        self.bytes_per_token_q8 = max(16, int(2 * self.block_count * self.head_count_kv * head_dim * 1 * swa_factor))
        self.bytes_per_token_f16 = self.bytes_per_token_q8 * 2

        # Calculate ideal context length for 16GB VRAM budget
        vram_budget_for_kv = max(0.5, 15.2 - self.size_gb - 0.6) * (1024 ** 3)
        max_safe_ctx_q8 = int(vram_budget_for_kv // max(1, self.bytes_per_token_q8))
        self.ideal_gpu_ctx = min(self.max_context_length, max(8192, (max_safe_ctx_q8 // 4096) * 4096))
        self.ideal_kv_quant = "q8_0" if self.ideal_gpu_ctx >= 32768 else "f16"

        # Detect companion draft models (dflash, mtp) in the same directory
        self.companion_draft_model = self._find_companion_draft(full_path.parent)

    def _extract_max_context_length(self, meta: Dict[str, Any]) -> int:
        arch = self.architecture
        keys = [
            f"{arch}.context_length",
            "llama.context_length",
            "qwen2.context_length",
            "gemma2.context_length",
            "gemma.context_length",
            "gpt_neox.context_length"
        ]
        for k in keys:
            if k in meta:
                return _to_int(meta[k], 32768)
        return 32768

    def _detect_quantization(self) -> str:
        match = re.search(r'(iq\d+_[a-z\d_]+|q\d+_[a-z\d_]+|mxfp\d+|f16|f32|q8_0)', self.filename, re.IGNORECASE)
        return match.group(0).upper() if match else "GGUF"

    def _classify_role(self) -> str:
        name = self.filename.lower()
        if "e4b" in name or "e2b" in name or "2b" in name or "3b" in name or "4b" in name or "mini" in name:
            return "VTuber"
        elif any(size in name for size in ["12b", "14b", "20b", "27b", "30b", "32b", "70b"]):
            return "Agent"
        return "VTuber" if self.size_gb < 6.0 else "Agent"

    def _find_companion_draft(self, directory: Path) -> Optional[Dict[str, Any]]:
        for p in directory.glob("*.gguf"):
            name = p.name.lower()
            if p != self.full_path and ("dflash" in name or "mtp" in name or "draft" in name):
                return {
                    "filename": p.name,
                    "full_path": str(p.resolve()),
                    "type": "dflash" if "dflash" in name else ("mtp" if "mtp" in name else "draft"),
                    "size_gb": round(p.stat().st_size / (1024 ** 3), 2)
                }
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.filename,
            "relative_path": self.relative_path,
            "full_path": str(self.full_path),
            "size_gb": self.size_gb,
            "architecture": self.architecture,
            "quantization": self.quantization,
            "recommended_role": self.recommended_role,
            "block_count": self.block_count,
            "gqa_ratio": f"{self.head_count}:{self.head_count_kv}",
            "moe_info": self.moe_info,
            "bytes_per_token_q8": self.bytes_per_token_q8,
            "max_context_length": self.max_context_length,
            "ideal_gpu_ctx": self.ideal_gpu_ctx,
            "ideal_kv_quant": self.ideal_kv_quant,
            "companion_draft_model": self.companion_draft_model
        }


class ModelScanner:
    def __init__(self, models_dir: str):
        self.models_dir = Path(models_dir)

    def scan(self) -> List[Dict[str, Any]]:
        if not self.models_dir.exists():
            return []

        models: List[ModelInfo] = []
        for root, _, files in os.walk(self.models_dir):
            for file in files:
                if file.lower().endswith(".gguf"):
                    file_lower = file.lower()
                    if "dflash" in file_lower or file_lower.startswith("mtp-") or "mtp_" in file_lower:
                        continue

                    full_path = Path(root) / file
                    try:
                        info = ModelInfo(full_path, self.models_dir)
                        models.append(info)
                    except Exception as e:
                        print(f"[ModelScanner] Error reading {file}: {e}")

        models.sort(key=lambda m: (m.recommended_role != "Agent", -m.size_gb))
        return [m.to_dict() for m in models]

    def resolve_model_path(self, model_identifier: str) -> Optional[str]:
        direct_path = Path(model_identifier)
        if direct_path.is_file():
            return str(direct_path.resolve())

        rel_path = self.models_dir / model_identifier
        if rel_path.is_file():
            return str(rel_path.resolve())

        for root, _, files in os.walk(self.models_dir):
            for file in files:
                if file == model_identifier or file.lower() == model_identifier.lower():
                    return str((Path(root) / file).resolve())

        return None
