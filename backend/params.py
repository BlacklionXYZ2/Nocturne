"""
llama.cpp Parameter Models & Argument Builder
==============================================
Defines strongly-typed configuration models for `LlamaServerParams` and `SamplingParams`.

Supports:
- Massive context windows up to 256k / 1M+ tokens (-c / --ctx-size)
- AMD ROCm GPU acceleration (--device ROCm0 -ngl 99)
- Speculative decoding / draft models (--model-draft for dflash / MTP)
- Flash attention (-fa) & quantized KV caching (-ctk / -ctv)
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class LlamaServerParams(BaseModel):
    """
    Configuration parameters passed to `llama-server.exe`.
    """

    # --------------------------------------------------------------------------
    # Model & Context Window Parameters
    # --------------------------------------------------------------------------
    ctx_size: int = Field(
        default=32768,
        ge=512,
        le=1048576,  # Supports up to 1M tokens
        description="Context window size in tokens (-c / --ctx-size). Supports 8k, 32k, 128k, 256k+."
    )

    # --------------------------------------------------------------------------
    # GPU Offloading & Acceleration (ROCm / CUDA)
    # --------------------------------------------------------------------------
    n_gpu_layers: int = Field(
        default=99,
        ge=0,
        description="Number of model layers to offload to GPU VRAM (-ngl / --n-gpu-layers). 99 = all layers."
    )

    device: str = Field(
        default="ROCm0",
        description="Target compute device (-dev / --device). 'ROCm0' for AMD Radeon RX 9070 XT."
    )

    flash_attn: bool = Field(
        default=True,
        description="Enables Flash Attention (-fa / --flash-attn)."
    )

    # --------------------------------------------------------------------------
    # Speculative Decoding / Draft Models (dflash, MTP)
    # --------------------------------------------------------------------------
    draft_model: Optional[str] = Field(
        default=None,
        description="Path to speculative draft model GGUF (e.g. dflash or mtp) to accelerate generation (--model-draft / -md)."
    )

    draft_gpu_layers: int = Field(
        default=99,
        ge=0,
        description="GPU layers for draft model offload (--gpu-layers-draft / -ngld)."
    )

    # --------------------------------------------------------------------------
    # KV Cache Quantization (VRAM Optimization)
    # --------------------------------------------------------------------------
    cache_type_k: str = Field(
        default="q8_0",
        description="KV Cache Key quantization type (-ctk: 'f16', 'q8_0', 'q4_0')."
    )

    cache_type_v: str = Field(
        default="q8_0",
        description="KV Cache Value quantization type (-ctv: 'f16', 'q8_0', 'q4_0')."
    )

    # --------------------------------------------------------------------------
    # Batch Processing & CPU Threads
    # --------------------------------------------------------------------------
    batch_size: int = Field(
        default=2048,
        ge=32,
        le=8192,
        description="Prompt evaluation batch size (-b / --batch-size)."
    )

    ubatch_size: int = Field(
        default=1024,
        ge=32,
        le=2048,
        description="Physical micro-batch size (-ub / --ubatch-size)."
    )

    threads: int = Field(
        default=0,
        ge=0,
        description="CPU compute threads (-t / --threads). 0 = auto-detect."
    )

    parallel: int = Field(
        default=1,
        ge=1,
        le=16,
        description="Number of simultaneous request slots (--parallel / -np)."
    )

    no_mmap: bool = Field(
        default=False,
        description="Disable memory mapping (--no-mmap)."
    )

    mlock: bool = Field(
        default=False,
        description="Lock model in memory (--mlock)."
    )

    def build_cli_args(self, model_path: str, host: str = "127.0.0.1", port: int = 8080) -> List[str]:
        """
        Compiles configuration model into command line arguments for `llama-server.exe`.
        """
        args = [
            "-m", model_path,
            "--host", host,
            "--port", str(port),
            "-c", str(self.ctx_size),
            "-ngl", str(self.n_gpu_layers),
            "-b", str(self.batch_size),
            "-ub", str(self.ubatch_size),
            "-np", str(self.parallel),
        ]

        if self.device and self.device.lower() != "auto":
            args.extend(["-dev", self.device])

        if self.flash_attn:
            args.extend(["--flash-attn", "on"])

        # Speculative Decoding / Draft model (dflash / MTP)
        if self.draft_model:
            args.extend(["--model-draft", self.draft_model])
            if self.draft_gpu_layers > 0:
                args.extend(["-ngld", str(self.draft_gpu_layers)])
            if self.device and self.device.lower() != "auto":
                args.extend(["--spec-draft-device", self.device])

        if self.cache_type_k and self.cache_type_k.lower() != "f16":
            args.extend(["-ctk", self.cache_type_k])

        if self.cache_type_v and self.cache_type_v.lower() != "f16":
            args.extend(["-ctv", self.cache_type_v])

        if self.threads > 0:
            args.extend(["-t", str(self.threads)])

        if self.no_mmap:
            args.append("--no-mmap")

        if self.mlock:
            args.append("--mlock")

        return args


class SamplingParams(BaseModel):
    """Sampling parameters for text generation."""

    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    top_p: float = Field(default=0.95, ge=0.0, le=1.0)
    min_p: float = Field(default=0.05, ge=0.0, le=1.0)
    top_k: int = Field(default=40, ge=0)
    repeat_penalty: float = Field(default=1.05, ge=1.0, le=2.0)
    presence_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)
    frequency_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1, le=65536)
    stop: Optional[List[str]] = Field(default=None)
