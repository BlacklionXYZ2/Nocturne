"""
Autonomous Agent Scheduler & Self-Prompting Engine
===================================================
Enables the local agent to prompt and direct itself autonomously on configurable intervals
or pending task queues, executing tools, reflecting into memory, and immediately sleeping
the AMD GPU to minimize electrical power draw (330W -> 18W) and prevent ambient heat build-up.
"""

import asyncio
import time
from typing import Optional, Dict, Any, Callable
from pathlib import Path

from .core import AgentEngine
from .tracker import broadcaster
from backend.llama_manager import LlamaServerManager


class AutonomousScheduler:
    """Manages scheduled background self-prompting cycles."""

    def __init__(
        self,
        agent: AgentEngine,
        llama_mgr: LlamaServerManager,
        config: Dict[str, Any],
        memory_dir: str = "memory"
    ):
        self.agent = agent
        self.llama_mgr = llama_mgr
        self.config = config
        self.memory_dir = Path(memory_dir)

        sched_cfg = config.get("autonomous_scheduler", {})
        self.enabled = sched_cfg.get("enabled", False)
        self.interval_minutes = sched_cfg.get("interval_minutes", 60)
        self.max_turns = sched_cfg.get("max_turns_per_cycle", 10)
        self.sleep_after_cycle = sched_cfg.get("sleep_gpu_after_cycle", True)
        self.prompt_template = sched_cfg.get("prompt_template", "")

        self._task_handle: Optional[asyncio.Task] = None
        self._is_running_cycle = False
        self.last_run_time: Optional[float] = None
        self.next_run_time: Optional[float] = None

    def start(self):
        """Starts the background scheduler loop."""
        if self._task_handle is None or self._task_handle.done():
            self._task_handle = asyncio.create_task(self._scheduler_loop())

    def stop(self):
        """Stops the scheduler loop."""
        if self._task_handle and not self._task_handle.done():
            self._task_handle.cancel()
            self._task_handle = None

    def update_settings(self, enabled: bool, interval_minutes: int, sleep_after_cycle: bool = True):
        """Updates scheduler settings dynamically."""
        self.enabled = enabled
        self.interval_minutes = max(5, interval_minutes)
        self.sleep_after_cycle = sleep_after_cycle
        if self.enabled:
            self.next_run_time = time.time() + (self.interval_minutes * 60)
        else:
            self.next_run_time = None

    async def run_cycle_now(self, custom_prompt: Optional[str] = None) -> Dict[str, Any]:
        """
        Executes a single autonomous self-prompting cycle immediately.
        """
        if self._is_running_cycle:
            return {"status": "busy", "message": "An autonomous cycle is already in progress."}

        self._is_running_cycle = True
        self.last_run_time = time.time()

        await broadcaster.emit("status", "⚡ [AUTONOMOUS] Waking GPU for self-prompting cycle...")

        try:
            # 1. Wake GPU
            awake = await asyncio.to_thread(self.llama_mgr.ensure_awake)
            if not awake:
                await broadcaster.emit("status", "❌ [ERROR] Could not wake GPU for autonomous cycle.")
                return {"status": "error", "message": "Failed to wake GPU."}

            # 2. Gather context and construct self-prompt
            task_queue_path = self.memory_dir / "task_queue.md"
            task_queue_content = ""
            if task_queue_path.is_file():
                task_queue_content = task_queue_path.read_text(encoding="utf-8")

            if custom_prompt:
                self_prompt = custom_prompt
            else:
                self_prompt = (
                    "You are Auri, executing an autonomous self-prompting cycle in Nocturne.\n\n"
                    f"### Current Task Queue:\n{task_queue_content}\n\n"
                    "Instructions:\n"
                    "1. Review pending tasks in task_queue.md.\n"
                    "2. If a task contains a `- Verify: <cmd>` check, execute the action and run the verification command to confirm it passes with Exit Code 0.\n"
                    "3. Formulate your reasoning inside a `<thought>` block.\n"
                    "4. Execute necessary tool actions.\n"
                    "5. If a task was completed and verified, update task_queue.md to mark it `[x]`.\n"
                    "6. Conclude by writing your reflections into memory/agent_thoughts.md."
                )

            await broadcaster.emit("status", "🤖 [AUTONOMOUS] Executing self-directed reasoning step...")

            # 3. Run agent ReAct loop with real-time WebSocket streaming
            async def _on_event(event_type: str, data: Any):
                await broadcaster.emit(event_type, data)

            result = await self.agent.run_task(
                prompt=self_prompt,
                max_turns=self.max_turns,
                on_event=_on_event
            )

            # 4. Power down / Sleep GPU to save electricity (330W -> 18W)
            if self.sleep_after_cycle:
                await asyncio.sleep(2)
                await asyncio.to_thread(self.llama_mgr.sleep)
                await broadcaster.emit("status", "💤 [POWER SAVER] GPU put to sleep (Unloaded from VRAM to cool GPU).")

            if self.enabled:
                self.next_run_time = time.time() + (self.interval_minutes * 60)

            return {
                "status": "completed",
                "final_answer": result.get("final_answer"),
                "turns_taken": result.get("turns_taken"),
                "tool_calls_count": len(result.get("tool_calls_made", []))
            }

        except Exception as e:
            await broadcaster.emit("status", f"❌ [ERROR] Autonomous cycle failed: {e}")
            return {"status": "error", "message": str(e)}

        finally:
            self._is_running_cycle = False

    async def _scheduler_loop(self):
        """Background coroutine that triggers runs at the configured interval."""
        while True:
            try:
                await asyncio.sleep(10)
                if self.enabled and not self._is_running_cycle:
                    now = time.time()
                    if self.next_run_time is None:
                        self.next_run_time = now + (self.interval_minutes * 60)
                    elif now >= self.next_run_time:
                        await self.run_cycle_now()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[AutonomousScheduler] Loop error: {e}")
                await asyncio.sleep(30)

    def get_status(self) -> Dict[str, Any]:
        """Returns current scheduler state."""
        return {
            "enabled": self.enabled,
            "interval_minutes": self.interval_minutes,
            "is_running_cycle": self._is_running_cycle,
            "last_run_time": self.last_run_time,
            "next_run_time": self.next_run_time,
            "sleep_after_cycle": self.sleep_after_cycle,
            "gpu_power_state": self.llama_mgr.power_state
        }
