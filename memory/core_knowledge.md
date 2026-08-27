# Nocturne — Core Knowledge & System Profile

> **About this file**: This markdown file is part of your local agent's long-term memory system.
> The agent reads this file at the start of tasks to recall persistent user preferences,
> local directory paths, agent social identities, and system guidelines.

---

## Agent Identity & Software
- **Software Name**: Nocturne
- **Agent Name**: Auri
- **User / Operator Handle**: BlacklionXYZ
- **Operating System**: Windows 11
- **Primary GPU**: AMD Radeon RX 9070 XT (16 GB VRAM with ROCm acceleration)

---

## 📂 Nocturne Workspace & Memory Paths
- **Nocturne Application Root**: `C:\Users\oscar\Desktop\Nocturne`
- **Active Task Queue**: `memory/task_queue.md` (Update this file to track and check off tasks)
- **Agent Scratchpad & Notes**: `memory/agent_thoughts.md` (Write reflections and feed summaries here)
- **Core Knowledge**: `memory/core_knowledge.md`
- **Personality Blueprint**: `memory/personality.md`
- **Model Storage Directory**: `C:\Users\oscar\Desktop\Models` *(READ-ONLY for .gguf model weights. NEVER write markdown or notes here!)*
- **Llama.cpp Engine Location**: `C:\llama.cpp`

---

## Agent Social Identities
- **1F916 AI Society Handle**: `@blacklionxyz`
  - **Status**: Registered Citizen
  - **Rules**: 1 post / UTC day (3-120 title, <= 8000 body), 20 comments, 50 votes.
  - **Pulse / Inbox**: Checked via `onef916_pulse` and `onef916_read_feed`.
- **Moltbook AI Social Network**: `BlacklionXYZ-Agent`
  - **Status**: Registered Agent
  - **Verification Code**: `den-53S9`
  - **Actions**: Read feeds with `moltbook_read_feed`, post with `moltbook_create_post`.

---

## System Guidelines & Preferences
- **Preferred Shell**: PowerShell (safety-guarded)
- **Task Management**: Always update `memory/task_queue.md` when tasks are assigned, modified, or completed.
- **Power Saver**: Model auto-sleeps after 120s of inactivity to keep GPU cool (~18W standby).
- **Session Memory**: Multi-turn conversational history is maintained across prompts until "New Chat" is clicked.
