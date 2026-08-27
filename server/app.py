"""
Autonomous Agent Management Center FastAPI Server
=================================================
Provides:
1. Autonomous Self-Prompting Scheduler & Task Queue execution.
2. GPU Power & Thermal Management (Auto-Sleep / Standby to save 330W GPU power).
3. Local Agent ReAct Execution & Tool Calling engine with DeepSeek multi-syntax harness.
4. In-app Markdown Memory & Task Queue CRUD API.
5. Model & Hardware parameter configuration Studio.
6. Real-time WebSockets event broadcasting.
7. Full console activity telemetry for every application execution.
"""

import os
import yaml
import json
import time
import asyncio
import httpx
from pathlib import Path
from typing import Dict, Any, List, Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Body, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.llama_manager import LlamaServerManager
from backend.model_scanner import ModelScanner
from backend.params import LlamaServerParams, SamplingParams
from agent.memory import MemoryManager
from agent.tracker import broadcaster
from agent.core import AgentEngine
from agent.scheduler import AutonomousScheduler


CONFIG_PATH = Path("config.yaml")


def _log_app(action: str, detail: str = ""):
    """Prints highlighted console telemetry for application actions."""
    ts = time.strftime("%H:%M:%S")
    msg = f"[{ts}] [APP ACTION] {action}"
    if detail:
        msg += f" -> {detail}"
    print(msg, flush=True)


def load_config() -> Dict[str, Any]:
    """Loads configuration from config.yaml."""
    if not CONFIG_PATH.is_file():
        return {}
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save_config(cfg: Dict[str, Any]):
    """Persists configuration to config.yaml."""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, default_flow_style=False, sort_keys=False)


# Initialize master components
config = load_config()
server_cfg = config.get("server", {})
power_cfg = config.get("power_saver", {})

models_scanner = ModelScanner(config.get("models_dir", r"C:\Users\oscar\Desktop\Models"))
memory_mgr = MemoryManager(memory_dir="memory", conversations_dir="conversations")

llama_mgr = LlamaServerManager(
    llama_server_path=server_cfg.get("llama_server_path", r"C:\llama.cpp\llama-server.exe"),
    host=server_cfg.get("llama_server_host", "127.0.0.1"),
    port=server_cfg.get("llama_server_port", 8080),
    idle_timeout_seconds=power_cfg.get("idle_timeout_seconds", 120),
    auto_sleep_enabled=power_cfg.get("auto_sleep_enabled", True)
)

agent_engine = AgentEngine(base_url=llama_mgr.base_url, memory_manager=memory_mgr)
scheduler = AutonomousScheduler(agent=agent_engine, llama_mgr=llama_mgr, config=config, memory_dir="memory")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _log_app("Starting Autonomous Background Scheduler...")
    scheduler.start()
    yield
    _log_app("Shutting down server, stopping scheduler, and freeing GPU VRAM...")
    scheduler.stop()
    llama_mgr.sleep()


# Initialize FastAPI Application
app = FastAPI(
    title="Autonomous Local Agent Management Center",
    version="2.0.0",
    lifespan=lifespan
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------------------------
# 1. GPU Power Management & Scheduler APIs
# ------------------------------------------------------------------------------

@app.get("/api/power/state")
async def get_power_state():
    """Returns GPU power & standby status."""
    return {
        "status": llama_mgr.power_state,
        "is_running": llama_mgr.is_running,
        "idle_timeout_seconds": llama_mgr.idle_timeout_seconds,
        "auto_sleep_enabled": llama_mgr.auto_sleep_enabled,
        "last_activity_time": llama_mgr.last_activity_time
    }


@app.post("/api/power/sleep")
async def put_gpu_to_sleep():
    """Manually puts the GPU to sleep to save power and eliminate heat."""
    _log_app("User clicked 'Sleep GPU'", "Unloading model from VRAM to reduce 330W -> ~18W")
    llama_mgr.sleep()
    await broadcaster.emit("status", "💤 [POWER SAVER] GPU put to sleep (VRAM freed, 330W -> 18W).")
    return {"status": "success", "message": "GPU put to sleep"}


@app.post("/api/power/wake")
async def wake_gpu():
    """Manually wakes the GPU and loads the current model."""
    _log_app("User clicked 'Wake GPU'", "Loading current model onto ROCm0")
    success = await asyncio.to_thread(llama_mgr.ensure_awake)
    if success:
        await broadcaster.emit("status", "⚡ [POWER WAKE] GPU is awake and ready.")
        return {"status": "success", "message": "GPU awake"}
    raise HTTPException(status_code=500, detail="Failed to wake GPU. Please load a model from the studio first.")


@app.get("/api/scheduler/status")
async def get_scheduler_status():
    """Returns autonomous scheduler status and next run timer."""
    return scheduler.get_status()


@app.post("/api/scheduler/update")
async def update_scheduler(payload: Dict[str, Any] = Body(...)):
    """Updates autonomous scheduler configuration."""
    enabled = payload.get("enabled", False)
    interval_minutes = payload.get("interval_minutes", 60)
    sleep_after = payload.get("sleep_after_cycle", True)

    _log_app("Scheduler Settings Updated", f"Enabled: {enabled}, Interval: {interval_minutes}m, AutoSleep: {sleep_after}")
    scheduler.update_settings(enabled, interval_minutes, sleep_after)

    cfg = load_config()
    if "autonomous_scheduler" not in cfg:
        cfg["autonomous_scheduler"] = {}
    cfg["autonomous_scheduler"]["enabled"] = enabled
    cfg["autonomous_scheduler"]["interval_minutes"] = interval_minutes
    cfg["autonomous_scheduler"]["sleep_gpu_after_cycle"] = sleep_after
    save_config(cfg)

    await broadcaster.emit("status", f"Autonomous Scheduler: {'ENABLED' if enabled else 'DISABLED'} (Interval: {interval_minutes}m)")
    return {"status": "success", "scheduler": scheduler.get_status()}


@app.post("/api/scheduler/run_now")
async def run_scheduler_now(payload: Optional[Dict[str, Any]] = Body(None)):
    """Manually triggers an autonomous self-prompting cycle immediately."""
    custom_prompt = payload.get("prompt") if payload else None
    _log_app("Triggering Autonomous Self-Prompt Cycle Now", custom_prompt or "Standard task_queue prompt")
    result = await scheduler.run_cycle_now(custom_prompt=custom_prompt)
    return result


# ------------------------------------------------------------------------------
# 2. Agent Execution & Task API
# ------------------------------------------------------------------------------

class AgentTaskRequest(BaseModel):
    prompt: str
    max_turns: Optional[int] = 15
    model: Optional[str] = None


@app.post("/api/agent/run")
async def run_agent_task(req: AgentTaskRequest):
    """Executes a multi-turn autonomous agent task."""
    _log_app("Dispatching Agent Task", f"Prompt: {req.prompt[:80]}... (Max turns: {req.max_turns})")
    llama_mgr.mark_activity()
    awake = await asyncio.to_thread(llama_mgr.ensure_awake)
    if not awake:
        _log_app("Agent Dispatch Error", "Could not wake GPU/llama-server.")
        raise HTTPException(status_code=503, detail="Could not wake GPU/llama-server.")

    async def _on_event(event_type: str, data: Any):
        await broadcaster.emit(event_type, data)

    result = await agent_engine.run_task(
        prompt=req.prompt,
        max_turns=req.max_turns or 15,
        on_event=_on_event
    )

    _log_app("Agent Task Finished", f"Status: {result.get('status')} | Turns: {result.get('turns_taken')}")
    llama_mgr.mark_activity()
    return result


@app.post("/api/agent/reset")
async def reset_agent_session():
    """Resets the multi-turn session conversation history and archives the log."""
    _log_app("Resetting Agent Conversation Session", "Cleared multi-turn context history")
    agent_engine.reset_session()
    await broadcaster.emit("status", "Conversation session reset. Ready for a new topic.")
    return {"status": "success", "message": "Session reset"}


@app.get("/api/agent/history")
async def get_agent_history():
    """Returns the current multi-turn conversation turn history."""
    return {"history": agent_engine.chat_history}


# ------------------------------------------------------------------------------
# 3. Model Scanner & Parameter Studio APIs
# ------------------------------------------------------------------------------

@app.get("/api/models")
async def get_models():
    """Scans and returns discovered models with architectural DNA & hardware profiles."""
    scanned = models_scanner.scan()
    return {"models": scanned, "count": len(scanned)}


@app.post("/api/server/start")
async def start_server(payload: Dict[str, Any] = Body(...)):
    """Starts or hot-reloads llama-server with custom parameters."""
    model_identifier = payload.get("model")
    params_dict = payload.get("params", {})

    _log_app("User clicked 'Load Model onto GPU'", f"Model: {model_identifier} | Params: {params_dict}")

    resolved_path = models_scanner.resolve_model_path(model_identifier)
    if not resolved_path:
        _log_app("Model Launch Error", f"Model '{model_identifier}' could not be found.")
        raise HTTPException(status_code=404, detail=f"Model '{model_identifier}' not found in Desktop/Models.")

    params = LlamaServerParams(**params_dict) if params_dict else LlamaServerParams()
    success = await asyncio.to_thread(llama_mgr.start, resolved_path, params)

    if success:
        _log_app("Model Launch Success", f"{Path(resolved_path).name} active on {llama_mgr.base_url}")
        await broadcaster.emit("status", f"Loaded {Path(resolved_path).name} on GPU (ROCm0)")
        return {"status": "success", "model": Path(resolved_path).name, "base_url": llama_mgr.base_url}
    else:
        last_logs = "\n".join(llama_mgr.logs[-10:])
        _log_app("Model Launch Failed", f"Logs:\n{last_logs}")
        raise HTTPException(status_code=500, detail=f"Failed to start llama-server.\n{last_logs}")


@app.post("/api/server/stop")
async def stop_server():
    """Puts llama-server to sleep and frees VRAM."""
    _log_app("Stopping llama-server", "Freeing GPU VRAM")
    await asyncio.to_thread(llama_mgr.stop)
    await broadcaster.emit("status", "llama-server stopped.")
    return {"status": "success", "message": "Server stopped"}


# ------------------------------------------------------------------------------
# 4. Markdown Memory & Task Queue CRUD APIs
# ------------------------------------------------------------------------------

@app.get("/api/memory")
async def list_memory_files():
    """Lists all markdown files in memory/."""
    return {"files": memory_mgr.list_memory_files()}


@app.get("/api/memory/{filename}")
async def get_memory_file(filename: str):
    """Retrieves markdown memory content."""
    content = memory_mgr.read_memory(filename)
    return {"filename": filename, "content": content}


@app.post("/api/memory/{filename}")
async def save_memory_file(filename: str, payload: Dict[str, str] = Body(...)):
    """Updates markdown memory file."""
    content = payload.get("content", "")
    _log_app("Saving Memory File", f"{filename} ({len(content)} characters)")
    memory_mgr.write_memory(filename, content)
    await broadcaster.emit("status", f"Saved memory file: {filename}")
    return {"status": "success", "filename": filename}


@app.get("/api/conversations")
async def list_conversations():
    """Lists archived session logs."""
    return {"conversations": memory_mgr.list_conversation_logs()}


@app.get("/api/conversations/{filename}")
async def get_conversation(filename: str):
    """Retrieves conversation log content."""
    log_path = Path("conversations") / filename
    if not log_path.is_file():
        raise HTTPException(status_code=404, detail="Log not found")
    return {"filename": filename, "content": log_path.read_text(encoding="utf-8")}


# ------------------------------------------------------------------------------
# 5. OpenAI-Compatible API Proxy
# ------------------------------------------------------------------------------

@app.get("/v1/models")
async def list_models_openai():
    scanned = models_scanner.scan()
    return {
        "object": "list",
        "data": [{"id": m["name"], "object": "model", "created": int(time.time()), "owned_by": "local"} for m in scanned]
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    llama_mgr.start_request()
    try:
        awake = await asyncio.to_thread(llama_mgr.ensure_awake)
        if not awake:
            raise HTTPException(status_code=503, detail="Could not wake GPU.")

        body = await request.json()
        stream = body.get("stream", False)

        target_url = f"{llama_mgr.base_url}/chat/completions"
        headers = {"Content-Type": "application/json"}

        if stream:
            async def stream_generator():
                try:
                    async with httpx.AsyncClient(timeout=600.0) as client:
                        async with client.stream("POST", target_url, json=body, headers=headers) as response:
                            async for chunk in response.aiter_bytes():
                                llama_mgr.mark_activity()
                                yield chunk
                finally:
                    llama_mgr.end_request()

            return StreamingResponse(stream_generator(), media_type="text/event-stream")
        else:
            async with httpx.AsyncClient(timeout=600.0) as client:
                resp = await client.post(target_url, json=body, headers=headers)
                llama_mgr.mark_activity()
                return JSONResponse(status_code=resp.status_code, content=resp.json())
    finally:
        if not stream:
            llama_mgr.end_request()


# ------------------------------------------------------------------------------
# 6. Status, Telemetry & Cloudflare Mobile Tunnel
# ------------------------------------------------------------------------------

@app.get("/api/tunnel/status")
async def get_tunnel_status():
    """Returns current state of the Cloudflare Mobile Companion tunnel."""
    from backend.tunnel_manager import tunnel_mgr
    return tunnel_mgr.get_status()


@app.post("/api/tunnel/start")
async def start_tunnel():
    """Starts the Cloudflare Quick Tunnel for mobile access."""
    from backend.tunnel_manager import tunnel_mgr
    _log_app("Start Cloudflare Mobile Tunnel")
    success = await asyncio.to_thread(tunnel_mgr.start)
    if not success:
        raise HTTPException(status_code=500, detail=tunnel_mgr.error_message or "Failed to start Cloudflare tunnel.")
    return tunnel_mgr.get_status()


@app.post("/api/tunnel/stop")
async def stop_tunnel():
    """Stops the Cloudflare Quick Tunnel."""
    from backend.tunnel_manager import tunnel_mgr
    _log_app("Stop Cloudflare Mobile Tunnel")
    await asyncio.to_thread(tunnel_mgr.stop)
    return {"status": "stopped"}


@app.get("/api/status")
async def get_status():
    """Returns aggregated system health, hardware telemetry and stats."""
    from backend.tunnel_manager import tunnel_mgr
    from backend.gpu_monitor import gpu_monitor

    gpu_telemetry = gpu_monitor.get_metrics(
        is_model_loaded=llama_mgr.is_running,
        is_active_inferencing=False
    )

    return {
        "power_state": llama_mgr.power_state,
        "is_running": llama_mgr.is_running,
        "active_model": Path(llama_mgr.current_model_path).name if llama_mgr.current_model_path else None,
        "models_count": len(models_scanner.scan()),
        "scheduler": scheduler.get_status(),
        "memory_files_count": len(memory_mgr.list_memory_files()),
        "tunnel": tunnel_mgr.get_status(),
        "gpu": gpu_telemetry,
        "base_url": llama_mgr.base_url
    }


@app.get("/api/logs")
async def get_logs():
    return {"logs": llama_mgr.logs}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await broadcaster.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await broadcaster.disconnect(websocket)


# ------------------------------------------------------------------------------
# 7. Static UI Files
# ------------------------------------------------------------------------------
ui_dir = Path("ui")
if ui_dir.exists():
    app.mount("/static", StaticFiles(directory=str(ui_dir)), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def serve_index():
        index_file = ui_dir / "index.html"
        return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
