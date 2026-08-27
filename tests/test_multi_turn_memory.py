import asyncio
import sys
from pathlib import Path

root_dir = Path('.').resolve()
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from agent.core import AgentEngine
from agent.memory import MemoryManager

def test_multi_turn_memory():
    mem = MemoryManager(memory_dir="memory", conversations_dir="conversations")
    agent = AgentEngine(memory_manager=mem)

    # Verify initial state
    assert len(agent.chat_history) == 0, "Chat history should initially be empty"

    # Simulate Turn 1: User introduces a topic
    agent.chat_history.append({"role": "user", "content": "I am working on project QuantumFalcon."})
    agent.chat_history.append({"role": "assistant", "content": "Acknowledged! I will keep QuantumFalcon in mind."})

    # Build messages for Turn 2
    messages = agent._build_messages("What was the name of my project?")
    
    # Check that previous turns are included in messages
    roles = [m["role"] for m in messages]
    contents = [m["content"] for m in messages]

    assert "system" in roles, "Must have system message"
    assert any("QuantumFalcon" in c for c in contents), "Turn 1 context must be present in Turn 2 messages"
    assert messages[-1]["content"] == "What was the name of my project?", "Last message should be new prompt"

    print("[SUCCESS] Multi-turn messages constructed properly with full conversation history:")
    for idx, m in enumerate(messages):
        snippet = m['content'][:60].replace('\n', ' ')
        print(f"  [{idx}] Role: {m['role']} | Content: {snippet}...")

    # Test reset_session
    agent.reset_session()
    assert len(agent.chat_history) == 0, "reset_session should clear chat history"
    print("[SUCCESS] reset_session properly cleared active context.")

if __name__ == "__main__":
    test_multi_turn_memory()
