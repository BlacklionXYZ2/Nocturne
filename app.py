"""
Nocturne — Autonomous Local Agent Management Center
====================================================
Desktop Entrypoint for Nocturne (Agent: Auri).
Launches the FastAPI backend and opens the native desktop window using Edge WebView2.

Features:
- Native Desktop Window: Dedicated interface for local agent monitoring.
- GPU Power Saver & Thermal Watchdog (330W -> 18W idle).
- Multi-Turn Conversational Memory & DeepSeek-Style Tool Harness.
- CLI Flags:
    python app.py          -> Opens Native Desktop Window (default)
    python app.py --web    -> Starts server and opens default web browser
    python app.py --server -> Starts headless backend server
"""

import sys
import time
import signal
import threading
import argparse
import webbrowser
import uvicorn
import webview

from server.app import app, llama_mgr, load_config


def run_uvicorn_server(host: str, port: int):
    """Runs the FastAPI server in a daemon thread."""
    config = uvicorn.Config(app=app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)
    server.run()


def cleanup():
    """Ensures background llama-server subprocesses are cleanly terminated."""
    print("\n[Nocturne] Shutting down...")
    try:
        llama_mgr.stop()
    except Exception as e:
        print(f"[Cleanup] Error stopping llama-server: {e}")


def main():
    parser = argparse.ArgumentParser(description="Nocturne — Autonomous Local Agent Management Center")
    parser.add_argument("--web", action="store_true", help="Launch in default web browser instead of native window")
    parser.add_argument("--server", action="store_true", help="Run headless server without GUI")
    parser.add_argument("--port", type=int, default=5000, help="Server port (default: 5000)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Server host (default: 127.0.0.1)")
    args = parser.parse_args()

    cfg = load_config()
    server_cfg = cfg.get("server", {})
    host = args.host or server_cfg.get("host", "127.0.0.1")
    port = args.port or server_cfg.get("port", 5000)

    # Register process exit handlers
    signal.signal(signal.SIGINT, lambda s, f: (cleanup(), sys.exit(0)))
    signal.signal(signal.SIGTERM, lambda s, f: (cleanup(), sys.exit(0)))

    # Start FastAPI server in background thread
    server_thread = threading.Thread(target=run_uvicorn_server, args=(host, port), daemon=True)
    server_thread.start()

    time.sleep(1.0)
    app_url = f"http://{host}:{port}"
    print(f"\n=======================================================")
    print(f"  NOCTURNE — Autonomous Local Agent Management Center")
    print(f"  Agent Persona      : Auri")
    print(f"  Web & UI Dashboard : {app_url}")
    print(f"  OpenAI API Proxy   : {app_url}/v1")
    print(f"=======================================================\n")

    if args.server:
        print("[INFO] Running in headless server mode. Press Ctrl+C to exit.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            cleanup()
            return

    if args.web:
        print(f"[INFO] Opening browser at {app_url}...")
        webbrowser.open(app_url)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            cleanup()
            return

    # Default: Native Desktop Application Window
    try:
        print("[INFO] Launching Native Nocturne Window...")
        window = webview.create_window(
            title="Nocturne — Autonomous Local Agent Center (Auri)",
            url=app_url,
            width=1280,
            height=840,
            min_size=(960, 600),
            background_color="#0f172a"
        )
        webview.start(private_mode=False)
    except Exception as e:
        print(f"[WARNING] Native window creation failed ({e}). Falling back to web browser...")
        webbrowser.open(app_url)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
    finally:
        cleanup()


if __name__ == "__main__":
    main()
