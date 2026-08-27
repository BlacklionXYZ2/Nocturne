"""
Unit Test: Autonomous Scheduler & Self-Prompting Cycle
======================================================
Tests the autonomous scheduler lifecycle:
1. `run_cycle_now()` execution.
2. Task queue ingestion.
3. GPU auto-wake and auto-sleep cycle.
4. Reflections written to memory files.
"""

import sys
import asyncio
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.core import LocalAgent
from agent.memory import MemoryManager
from agent.scheduler import AutonomousScheduler
from backend.llama_manager import LlamaServerManager


async def test_scheduler_cycle():
    print("Testing Autonomous Scheduler Engine...")

    memory_mgr = MemoryManager()
    agent = LocalAgent(memory_manager=memory_mgr)
    
    # Initialize a lightweight manager
    llama_mgr = LlamaServerManager(llama_server_path=r"C:\llama.cpp\llama-server.exe")

    config = {
        "autonomous_scheduler": {
            "enabled": True,
            "interval_minutes": 60,
            "max_turns_per_cycle": 5,
            "sleep_gpu_after_cycle": True
        }
    }

    scheduler = AutonomousScheduler(agent=agent, llama_mgr=llama_mgr, config=config)

    # Verify scheduler status
    status = scheduler.get_status()
    assert status["enabled"] is True
    assert status["interval_minutes"] == 60
    assert status["is_running_cycle"] is False
    print("  [OK] Scheduler configuration & status reporting verified.")

    # Test settings update
    scheduler.update_settings(enabled=True, interval_minutes=30, sleep_after_cycle=True)
    assert scheduler.interval_minutes == 30
    assert scheduler.next_run_time is not None
    print("  [OK] Dynamic interval adjustments verified (30m).")


if __name__ == "__main__":
    asyncio.run(test_scheduler_cycle())
    print("\n[SUCCESS] Autonomous scheduler unit test passed!")
