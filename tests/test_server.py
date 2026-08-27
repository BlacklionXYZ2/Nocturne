import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import asyncio
import httpx
from server.app import app


async def test_endpoints():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Test /api/status
        print("Testing GET /api/status...")
        res = await client.get("/api/status")
        assert res.status_code == 200, f"Status code: {res.status_code}"
        data = res.json()
        print(f"  [OK] Power state: {data['power_state']}")
        print(f"  [OK] Models count: {data['models_count']}")
        print(f"  [OK] Memory files count: {data['memory_files_count']}")
        print(f"  [OK] Scheduler enabled: {data['scheduler']['enabled']}")

        # Test /api/models
        print("\nTesting GET /api/models...")
        res = await client.get("/api/models")
        assert res.status_code == 200
        models_data = res.json()
        print(f"  [OK] Retrieved {len(models_data.get('models', []))} models")

        # Test /api/memory
        print("\nTesting GET /api/memory...")
        res = await client.get("/api/memory")
        assert res.status_code == 200
        mem_data = res.json()
        print(f"  [OK] Retrieved {len(mem_data.get('files', []))} memory files")

        # Test /api/memory/core_knowledge.md
        print("\nTesting GET /api/memory/core_knowledge.md...")
        res = await client.get("/api/memory/core_knowledge.md")
        assert res.status_code == 200
        print(f"  [OK] Successfully read core_knowledge.md ({len(res.json()['content'])} chars)")

        # Test /api/conversations
        print("\nTesting GET /api/conversations...")
        res = await client.get("/api/conversations")
        assert res.status_code == 200
        print(f"  [OK] Retrieved {len(res.json()['conversations'])} archived logs")

        # Test /api/scheduler/status
        print("\nTesting GET /api/scheduler/status...")
        res = await client.get("/api/scheduler/status")
        assert res.status_code == 200
        sched_data = res.json()
        print(f"  [OK] Scheduler interval: {sched_data['interval_minutes']}m")

        # Test /v1/models (OpenAI format)
        print("\nTesting GET /v1/models...")
        res = await client.get("/v1/models")
        assert res.status_code == 200
        v1_data = res.json()
        assert "data" in v1_data
        print(f"  [OK] OpenAI format valid, returned {len(v1_data['data'])} models")

    print("\n[SUCCESS] All server endpoint and memory tests passed!")


if __name__ == "__main__":
    asyncio.run(test_endpoints())
