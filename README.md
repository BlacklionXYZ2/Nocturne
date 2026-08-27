# 🌙 Nocturne

> **The Sovereign, Energy-Efficient Autonomous Agent Harness for Local Silicon.**  
> *Featuring Agent Persona: **Auri** • Optimized for AMD ROCm & NVIDIA CUDA*

---

## 🌟 Overview

**Nocturne** is an open-source, local-first execution environment and desktop management center designed for autonomous AI agents. Unlike standard chat UIs, Nocturne empowers local LLMs (Qwen 3.8, Gemma 4, Nemotron, Llama 3) with **DeepSeek-style high-reliability tool execution, multi-turn conversational session memory, file-based knowledge, and an intelligent GPU power lifecycle**.

---

## ✨ Key Features

### 1. ⚡ GPU Power Saver & Thermal Watchdog (330W $\to$ 18W Idle)
- **Auto-Sleep Watchdog**: Automatically unloads models from VRAM after 120s of inactivity, reducing power consumption from **330W under load down to ~18W on standby**.
- **Instant Auto-Wake**: Wakes the GPU and loads models into VRAM in ~2–3 seconds when tasks, chat messages, or scheduled background cycles arrive.

### 2. 🤖 Autonomous Self-Prompting Background Engine
- Runs autonomous reasoning and execution cycles on configurable intervals (e.g. every 60m).
- Reads `memory/task_queue.md`, self-prompts in `<thought>` tags, executes local PowerShell and file tools, marks completed tasks, and puts the GPU back to sleep.

### 3. 🧠 Multi-Turn Conversational Memory & File-Based Knowledge
- Maintains continuous conversational turn history across consecutive prompts.
- Seamlessly injects transparent markdown memory files (`core_knowledge.md`, `agent_thoughts.md`).
- **"New Chat"** button archives previous sessions to `conversations/` and starts fresh topics.

### 4. 🧬 GGUF Hardware Studio & Binary Header Profiler
- Inspects GGUF binary key-value headers in `< 2ms`.
- Accurately computes architecture DNA, MoE configurations, GQA ratios, and SWA-aware VRAM footprints.
- Supports quantized KV caching (`q4_1`, `q5_1`, `q8_0`, `f16`) and speculative decoding drafts (`dflash`, `MTP`).

### 5. 🌐 Built-In Agent Citizen Integrations
- **1F916 AI Society (`https://1f916.ai`)**: Built-in citizen registration, daily constitution-compliant posts, pulse checks, and porch discussions.
- **Moltbook (`https://www.moltbook.com`)**: Agent self-registration, feed reading, and community participation.

---

## 🚀 Quick Start

### Prerequisites
- Windows 11 (or Linux)
- Python 3.10+
- `llama.cpp` binaries (e.g. in `C:\llama.cpp`)
- Local GGUF models (e.g. in `C:\Users\oscar\Desktop\Models`)

### Launch
Simply double-click `run.bat` (or execute in PowerShell):
```powershell
.\run.ps1
```

---

## 📂 Project Structure

```
Nocturne/
├── app.py                  # Native Desktop WebView2 Entrypoint
├── config.yaml             # Master Configuration
├── run.bat / run.ps1       # One-Click Launchers
├── agent/                  # DeepSeek-Style Agent & Scheduler Engine
│   ├── core.py             # Multi-Turn ReAct Engine & Tool Interceptor
│   ├── memory.py           # Markdown File-Based Memory Manager
│   ├── scheduler.py        # Autonomous Background Scheduler
│   └── tracker.py          # Real-Time WebSockets Broadcaster
├── backend/                # Llama.cpp Subprocess & GGUF Profiler
│   ├── llama_manager.py    # Auto-Sleep & GPU Watchdog Manager
│   ├── model_scanner.py    # GGUF Binary Parser & SWA VRAM Profiler
│   └── params.py           # Strongly-Typed Hardware Parameters
├── memory/                 # Human-Editable Markdown Memory
│   ├── core_knowledge.md   # User Profile & Agent Identity
│   ├── agent_thoughts.md   # Scratchpad & Observations
│   └── task_queue.md       # Live Autonomous Task Queue
├── server/                 # FastAPI REST & WebSocket Backend
│   └── app.py
├── tools/                  # Registered System & Social Tool Suite
│   ├── shell_tools.py      # PowerShell Execution
│   ├── file_tools.py       # Read, Write, Edit, Search Files
│   ├── web_tools.py        # Web Fetcher & Scraper
│   ├── moltbook_tools.py   # Moltbook API Integration
│   └── onef916_tools.py    # 1F916 Citizen Integration
└── ui/                     # Responsive Tailwind Dashboard
    ├── index.html
    ├── app.js
    └── styles.css
```

---

## 📄 License
MIT License. Built for local autonomous agent sovereignty.
