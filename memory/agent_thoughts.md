# Agent Working Memory & Scratchpad

> **About this file**: This file acts as the autonomous agent's persistent scratchpad.
> The agent logs active goals, progress on ongoing tasks, discoveries, and architectural notes here.
> It helps the agent resume multi-step workflows without losing track across sessions.

---

## Active Tasks & Status
- **Current Project**: Local Agent & VTuber Management Center setup.
- **Status**: Initialized. Ready for autonomous tasks and model serving.

---

## Technical Notes & Environment Findings
- `llama-server.exe` supports `--device ROCm0` for full GPU offloading to the AMD Radeon RX 9070 XT.
- Model directory `C:\Users\oscar\Desktop\Models` contains multiple quantized GGUFs:
  - `Qwen3.8-27B-UD-IQ4_XS.gguf`
  - `gemma-4-12b-it-Q4_K_M.gguf`
  - `Gemma4-12B-QAT-Uncensored...gguf`
  - `gemma-4-E4B-it-Q4_K_M.gguf`
  - `Gemma-4-E2B-Uncensored...gguf`
  - `NVIDIA-Nemotron-3.5-Lightning-30B-A3B-IQ3_M.gguf`
  - `gpt-oss-20b-MXFP4.gguf`
  - `Muse-Glimmer-30B-UD-Q3_K_XL.gguf`

---

## Working Scratchpad
- *Agent records notes, hypotheses, and intermediate findings here during long-running tasks.*
