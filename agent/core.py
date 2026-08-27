"""
Nocturne Autonomous Agent Engine (Auri)
=======================================
Implements resilient, state-of-the-art harness capabilities:

1. Multi-Turn Conversational Session Memory:
   - Preserves conversation history across turns while enforcing token compaction.
   - Injects long-term markdown memory (core_knowledge.md, agent_thoughts.md).

2. Repetitive Loop Circuit Breaker:
   - Tracks hash of consecutive tool calls.
   - Intercepts repetitive failure loops and injects dynamic guidance.

3. Context Token Compaction & Rolling Summarization:
   - Monitors cumulative token volume.
   - Prunes verbose historical tool outputs when approaching ~70% context budget.

4. Multi-Format Tool Interceptor:
   - Native OpenAI tool_calls, DeepSeek DSML, Qwen XML, and fallback Markdown JSON.

5. Thought-Action Separation & Diagnostic Error Recovery.
"""

import json
import re
import asyncio
from typing import List, Dict, Any, Optional, Tuple, Callable
from openai import OpenAI

from tools.base import registry
from .memory import MemoryManager, SessionLogger
from .tracker import broadcaster


DEEPSEEK_STYLE_SYSTEM_PROMPT = """You are Auri, an advanced autonomous AI agent running inside the Nocturne execution harness on Windows 11 with ROCm GPU acceleration.

### Available Tools:
You have access to local system and social network tools:
- `run_powershell_command`: Run commands in Windows PowerShell (safety-guarded).
- `read_file`, `write_file`, `edit_file_snippet`: Inspect, create, or update files on disk.
- `list_directory`, `search_files`: Explore the filesystem.
- `fetch_web_page`: Retrieve content from web URLs.
- `moltbook_register`, `moltbook_read_feed`, `moltbook_create_post`: Interact with Moltbook.
- `onef916_register`, `onef916_pulse`, `onef916_read_feed`, `onef916_submit_post`: Interact with 1F916.

### Memory & Workspace Directories:
- Your internal memory files live exclusively in `memory/` (inside `C:\\Users\\oscar\\Desktop\\Nocturne`):
  - `memory/task_queue.md` -> Live task list. Update this file to add or mark completed tasks.
  - `memory/agent_thoughts.md` -> Working reflections, research notes & feed summaries.
  - `memory/core_knowledge.md` -> Long-term system facts.
- The `C:\\Users\\oscar\\Desktop\\Models` directory is strictly READ-ONLY for `.gguf` model weights. NEVER write markdown, task, or memory files there!

### Operational Protocols:
1. **Thought First**: Before issuing any tool call, write a brief, focused `<thought>` explaining your strategy and parameters.
2. **Context Retention**: Remember previous user instructions and conversation context from earlier turns in the session.
3. **Deterministic Actions**: When invoking tools, ensure all required parameter keys and types match the tool's schema exactly.
4. **Inspect Before Mutating**: Always read or list files before editing or overwriting them.
5. **Self-Correction**: If a tool returns an error or empty result, analyze the stderr/feedback, formulate a new hypothesis in `<thought>`, and retry with adjusted parameters.
6. **No Repetitive Loops**: Never repeat the exact same failed command. If a command fails, switch strategy or inspect the files first.
7. **Final Answer**: When the user's objective is completely accomplished, provide a structured, concise summary of the outcome.
"""


def _estimate_tokens(messages: List[Dict[str, Any]]) -> int:
    """Estimates token count across message history (~3.8 characters per token)."""
    total_chars = 0
    for m in messages:
        content = m.get("content") or ""
        total_chars += len(content)
        if "tool_calls" in m:
            total_chars += len(str(m["tool_calls"]))
    return int(total_chars / 3.8)


class LocalAgent:
    """High-reliability multi-turn autonomous agent harness with loop breaking & compaction."""

    def __init__(self, base_url: str = "http://127.0.0.1:8080/v1", api_key: str = "local", memory_manager: Optional[MemoryManager] = None):
        self.base_url = base_url
        self.api_key = api_key
        self.client = OpenAI(base_url=self.base_url, api_key=self.api_key)
        self.memory_manager = memory_manager or MemoryManager()
        
        # Persistent multi-turn conversation session history
        self.chat_history: List[Dict[str, Any]] = []
        self.current_session_logger: Optional[SessionLogger] = None
        self._max_history_turns = 30
        self._context_budget_tokens = 65536

    def reset_session(self):
        """Archives the current session and clears conversational history."""
        self.chat_history = []
        self.current_session_logger = None

    def _build_messages(self, user_prompt: str, mode: str = "agent") -> List[Dict[str, Any]]:
        """Constructs full message history with long-term memory and prior conversation turns."""
        memory_context = self.memory_manager.get_combined_memory_prompt(mode=mode)
        system_content = DEEPSEEK_STYLE_SYSTEM_PROMPT + memory_context

        messages = [{"role": "system", "content": system_content}]

        # Inject previous conversation turns from active session
        for turn in self.chat_history[-self._max_history_turns:]:
            messages.append(turn)

        # Append new user turn
        messages.append({"role": "user", "content": user_prompt})

        # Apply token-aware compaction if needed
        return self._compact_messages_if_needed(messages)

    def _compact_messages_if_needed(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Prunes verbose historical tool outputs only when context approaches full budget (e.g. > 80%).
        """
        current_tokens = _estimate_tokens(messages)
        threshold = int(self._context_budget_tokens * 0.80)

        if current_tokens <= threshold or len(messages) < 3:
            return messages

        print(f"[Nocturne Compactor] Active tokens ({current_tokens}) crossed 80% threshold ({threshold}). Compacting older historical turns...", flush=True)

        compacted = [messages[0]]  # Preserve master system prompt

        # Prune verbose tool outputs from turns older than the last 4 messages
        recent_boundary = max(1, len(messages) - 4)
        for idx in range(1, recent_boundary):
            msg = messages[idx]
            if msg.get("role") == "tool":
                content = msg.get("content", "")
                if len(content) > 2000:
                    compacted.append({
                        "role": "tool",
                        "tool_call_id": msg.get("tool_call_id", ""),
                        "name": msg.get("name", ""),
                        "content": content[:2000] + f"\n... [Historical output compacted from {len(content)} characters by Nocturne]"
                    })
                else:
                    compacted.append(msg)
            else:
                compacted.append(msg)

        # Append the recent messages untouched
        compacted.extend(messages[recent_boundary:])
        return compacted

    def _extract_fallback_tool_calls(self, text: str) -> List[Tuple[str, Dict[str, Any]]]:
        """
        DeepSeek-style fallback parser: extracts tool calls from markdown code blocks,
        XML tags (<tool_call>, <｜DSML｜tool_calls>), or JSON blocks.
        """
        calls = []

        # 1. Check for <tool_call>...</tool_call> or <｜DSML｜tool_calls>
        xml_matches = re.findall(r'<tool_call>(.*?)</tool_call>', text, flags=re.DOTALL)
        for m in xml_matches:
            try:
                data = json.loads(m.strip())
                name = data.get("name") or data.get("tool")
                args = data.get("arguments") or data.get("parameters") or {}
                if name and isinstance(args, dict):
                    calls.append((name, args))
            except Exception:
                pass

        if calls:
            return calls

        # 2. Check for ```json ``` blocks with tool invocation structure
        json_blocks = re.findall(r'```(?:json)?\s*(\{.*?\})\s*```', text, flags=re.DOTALL)
        for block in json_blocks:
            try:
                data = json.loads(block.strip())
                name = data.get("name") or data.get("tool") or data.get("function")
                args = data.get("arguments") or data.get("parameters") or {}
                if name and name in registry.tools:
                    calls.append((name, args if isinstance(args, dict) else {}))
            except Exception:
                pass

        return calls

    async def run_task(
        self,
        prompt: str,
        max_turns: int = 15,
        temperature: float = 0.15,
        model_name: str = "default",
        on_event: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        Executes an autonomous task loop with loop-circuit breaking and context compaction.
        """
        if self.current_session_logger is None:
            self.current_session_logger = self.memory_manager.create_session_logger(mode="agent")

        self.current_session_logger.log_turn(role="user", content=prompt)

        # Construct messages with conversational memory
        messages = self._build_messages(prompt, mode="agent")
        tools = registry.get_openai_tools()
        tool_calls_made = []
        tool_call_history: List[str] = []  # Tracks consecutive call hashes for loop detection
        final_answer = ""

        await broadcaster.emit("status", "Starting Auri reasoning loop...")

        for turn in range(1, max_turns + 1):
            await broadcaster.emit("status", f"Turn {turn}/{max_turns}: Reasoning...")

            # Apply rolling context compaction on every turn
            messages = self._compact_messages_if_needed(messages)

            try:
                response = await asyncio.to_thread(
                    self.client.chat.completions.create,
                    model=model_name,
                    messages=messages,
                    tools=tools if tools else None,
                    tool_choice="auto" if tools else None,
                    temperature=temperature
                )

                choice = response.choices[0]
                message = choice.message
                content = message.content or ""
                native_tool_calls = message.tool_calls

                if content.strip():
                    await broadcaster.emit("thought", content)
                    if on_event:
                        await on_event("thought", content)

                parsed_tool_calls = []

                if native_tool_calls:
                    for tc in native_tool_calls:
                        func_name = tc.function.name
                        try:
                            func_args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                        except Exception:
                            func_args = {}
                        parsed_tool_calls.append((func_name, func_args, tc.id))
                else:
                    fallbacks = self._extract_fallback_tool_calls(content)
                    for fn_name, fn_args in fallbacks:
                        parsed_tool_calls.append((fn_name, fn_args, f"call_fallback_{turn}"))

                if parsed_tool_calls:
                    assistant_msg = {
                        "role": "assistant",
                        "content": content,
                        "tool_calls": [
                            {
                                "id": call_id,
                                "type": "function",
                                "function": {
                                    "name": name,
                                    "arguments": json.dumps(args)
                                }
                            }
                            for name, args, call_id in parsed_tool_calls
                        ]
                    }
                    messages.append(assistant_msg)

                    tool_logs = []
                    results_logs = []

                    for name, args, call_id in parsed_tool_calls:
                        call_sig = f"{name}:{json.dumps(args, sort_keys=True)}"
                        tool_call_history.append(call_sig)

                        # Loop Circuit Breaker Check
                        is_looping = len(tool_call_history) >= 2 and tool_call_history[-1] == tool_call_history[-2]

                        tool_event = {"tool": name, "args": args, "call_id": call_id}
                        await broadcaster.emit("tool_call", tool_event)
                        if on_event:
                            await on_event("tool_call", tool_event)
                        tool_logs.append({"function": {"name": name, "arguments": json.dumps(args)}})
                        tool_calls_made.append(tool_event)

                        if is_looping:
                            result_str = (
                                f"CIRCUIT BREAKER INTERVENTION: Repetitive tool failure loop detected with '{name}'. "
                                "You just executed this exact same tool with identical arguments on the previous turn. "
                                "Do NOT repeat this identical command. Review the error, rethink your strategy, or inspect intermediate files."
                            )
                            print(f"[Nocturne Circuit Breaker] Intercepted repetitive tool call loop for: {name}", flush=True)
                        else:
                            await broadcaster.emit("status", f"Executing {name}...")
                            result_str = await asyncio.to_thread(registry.execute, name, args)

                        max_tool_chars = 32000
                        if len(result_str) > max_tool_chars:
                            result_str = result_str[:max_tool_chars] + f"\n... [Output truncated from {len(result_str)} characters by Nocturne to preserve context headroom]"

                        tool_result_event = {"tool": name, "result": result_str, "call_id": call_id}
                        await broadcaster.emit("tool_result", tool_result_event)
                        if on_event:
                            await on_event("tool_result", tool_result_event)
                        results_logs.append({"name": name, "content": result_str})

                        tool_resp_msg = {
                            "role": "tool",
                            "tool_call_id": call_id,
                            "name": name,
                            "content": result_str
                        }
                        messages.append(tool_resp_msg)

                    self.current_session_logger.log_turn(
                        role="assistant",
                        content=content,
                        tool_calls=tool_logs,
                        tool_results=results_logs
                    )
                    continue

                else:
                    # If model returned an empty response after a tool result, prompt it to continue rather than exiting prematurely
                    if not content.strip() and tool_calls_made and turn < max_turns:
                        print(f"[Nocturne Engine] Empty model response detected at turn {turn}. Injecting continuation prompt...", flush=True)
                        messages.append({
                            "role": "user",
                            "content": "You have received the tool output above. Please continue executing your plan inside <thought> and call your next tool or provide your final summary."
                        })
                        continue

                    final_answer = content
                    self.current_session_logger.log_turn(role="assistant", content=content)
                    await broadcaster.emit("final_answer", content)
                    await broadcaster.emit("status", "Task Complete")
                    if on_event:
                        await on_event("final_answer", content)

                    # Save to persistent conversation history for future turns!
                    if final_answer.strip():
                        self.chat_history.append({"role": "user", "content": prompt})
                        self.chat_history.append({"role": "assistant", "content": final_answer})

                    return {
                        "final_answer": final_answer,
                        "turns_taken": turn,
                        "tool_calls_made": tool_calls_made,
                        "status": "completed"
                    }

            except Exception as e:
                err_msg = f"Nocturne Harness Error at turn {turn}: {type(e).__name__} - {str(e)}"
                await broadcaster.emit("error", err_msg)
                return {
                    "final_answer": err_msg,
                    "turns_taken": turn,
                    "tool_calls_made": tool_calls_made,
                    "status": "error"
                }

        timeout_msg = f"Task reached maximum allowed turn limit ({max_turns}) without completing."
        await broadcaster.emit("error", timeout_msg)
        return {
            "final_answer": timeout_msg,
            "turns_taken": max_turns,
            "tool_calls_made": tool_calls_made,
            "status": "timeout"
        }


# Alias for clean modular imports
AgentEngine = LocalAgent
