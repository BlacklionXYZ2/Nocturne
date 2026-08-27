"""
llama-server Subprocess & GPU Power Saver Lifecycle Manager
===========================================================
Supervises the execution of `llama-server.exe` (located in `C:\\llama.cpp`).

Key Capabilities:
1. Spawns `llama-server.exe` with AMD ROCm GPU acceleration flags (--device ROCm0 -ngl 99).
2. Auto-Sleep / Power Saver: Automatically unloads the model from VRAM after N seconds of
   inactivity, dropping AMD Radeon RX 9070 XT power draw from 330W to ~18W idle.
3. On-Demand Auto-Wake: Seamlessly wakes up and loads the model into VRAM when a new task or
   scheduled cycle arrives.
4. Threaded health check & stream capturing for real-time WebSockets telemetry.
"""

import os
import sys
import time
import socket
import threading
import subprocess
import httpx
from typing import Optional, Dict, Any, List
from pathlib import Path

from .params import LlamaServerParams


class LlamaServerManager:
    """Controls the lifecycle, health, and power-saving sleep of llama-server."""

    def __init__(
        self,
        llama_server_path: str = r"C:\llama.cpp\llama-server.exe",
        host: str = "127.0.0.1",
        port: int = 8080,
        idle_timeout_seconds: int = 120,
        auto_sleep_enabled: bool = True
    ):
        self.llama_server_path = Path(llama_server_path)
        self.host = host
        self.port = port
        self.idle_timeout_seconds = idle_timeout_seconds
        self.auto_sleep_enabled = auto_sleep_enabled

        self.process: Optional[subprocess.Popen] = None
        self.current_model_path: Optional[str] = None
        self.current_params: Optional[LlamaServerParams] = None
        self.last_activity_time: float = time.time()
        self.logs: List[str] = []
        self._max_log_lines = 300
        self._active_requests = 0
        self._lock = threading.RLock()  # Re-entrant lock to prevent self-deadlocks

        # Start background power watchdog thread
        self._watchdog_running = True
        self._watchdog_thread = threading.Thread(target=self._idle_watchdog_loop, daemon=True)
        self._watchdog_thread.start()

    def start_request(self):
        """Notifies the manager that an inference request has started."""
        with self._lock:
            self._active_requests += 1
            self.mark_activity()

    def end_request(self):
        """Notifies the manager that an inference request has completed."""
        with self._lock:
            self._active_requests = max(0, self._active_requests - 1)
            self.mark_activity()

    def is_computing(self) -> bool:
        """Queries llama-server /slots to check if slots are actively processing tokens."""
        if self._active_requests > 0:
            return True
        if not self.is_running:
            return False
        try:
            url = f"http://{self.host}:{self.port}/slots"
            with httpx.Client(timeout=0.8) as client:
                res = client.get(url)
                if res.status_code == 200:
                    slots = res.json()
                    for slot in slots:
                        if slot.get("is_processing") or slot.get("state") == 1:
                            return True
        except Exception:
            pass
        return False

    @property
    def is_running(self) -> bool:
        """Returns True if the llama-server subprocess is active and responding."""
        if self.process is None:
            return False
        if self.process.poll() is not None:
            return False
        return self.check_health()

    @property
    def power_state(self) -> str:
        """Returns 'active' if running on GPU, or 'sleeping' if unloaded from VRAM."""
        return "active" if self.is_running else "sleeping"

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}/v1"

    def mark_activity(self):
        """Notifies the manager that an inference or agent request just took place."""
        self.last_activity_time = time.time()

    def check_health(self) -> bool:
        """Queries llama-server's /health endpoint to verify responsiveness."""
        url = f"http://{self.host}:{self.port}/health"
        try:
            with httpx.Client(timeout=1.0) as client:
                res = client.get(url)
                return res.status_code == 200
        except Exception:
            return False

    def is_port_in_use(self) -> bool:
        """Checks if the configured port is occupied."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            return s.connect_ex((self.host, self.port)) == 0

    def start(self, model_path: str, params: Optional[LlamaServerParams] = None, timeout_seconds: int = 75) -> bool:
        """
        Launches `llama-server.exe` with the designated GGUF model and hardware parameters.
        """
        with self._lock:
            self.stop()

            # Ensure no stray orphan llama-server processes are hogging ROCm or port 8080
            if sys.platform == "win32":
                try:
                    subprocess.run(
                        ["taskkill", "/F", "/IM", "llama-server.exe"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                except Exception:
                    pass
                time.sleep(0.3)

            if not self.llama_server_path.is_file():
                self._log(f"[APP ERROR] llama-server executable not found at: {self.llama_server_path}")
                return False

            if not os.path.isfile(model_path):
                self._log(f"[APP ERROR] Model file not found at: {model_path}")
                return False

            if params is None:
                params = LlamaServerParams()

            self.current_model_path = model_path
            self.current_params = params

            cli_args = [str(self.llama_server_path)] + params.build_cli_args(
                model_path=model_path,
                host=self.host,
                port=self.port
            )

            cmd_str = " ".join(cli_args)
            self._log(f"[APP CMD] Spawning llama-server onto GPU (ROCm0):")
            print(f"\n>>> [APP CMD EXECUTION] {cmd_str}\n", flush=True)

            try:
                creation_flags = 0
                if sys.platform == "win32":
                    creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP

                self.process = subprocess.Popen(
                    cli_args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                    creationflags=creation_flags
                )

                print(f"[APP CMD] Process started with PID: {self.process.pid}", flush=True)

                def _reader():
                    if self.process and self.process.stdout:
                        try:
                            for line in iter(self.process.stdout.readline, ''):
                                if line:
                                    clean_line = line.strip()
                                    self._log(clean_line)
                                    print(f"  [llama-server PID {self.process.pid if self.process else '?'}] {clean_line}", flush=True)
                        except Exception:
                            pass
                        finally:
                            try:
                                self.process.stdout.close()
                            except Exception:
                                pass

                t = threading.Thread(target=_reader, daemon=True)
                t.start()

                start_time = time.time()
                self._log("[APP INFO] Loading model weights into VRAM... Waiting for health check...")
                print("[APP INFO] Loading model weights into VRAM... Waiting for health check...", flush=True)

                while time.time() - start_time < timeout_seconds:
                    if self.process.poll() is not None:
                        self._log(f"[APP ERROR] Process exited early with return code {self.process.returncode}")
                        print(f"[APP ERROR] Process exited early with return code {self.process.returncode}", flush=True)
                        return False
                    if self.check_health():
                        self.mark_activity()
                        self._log(f"[APP READY] Model loaded! Server active on {self.base_url}")
                        print(f"\n>>> [APP STATUS] [SUCCESS] Model is loaded and active on {self.base_url}!\n", flush=True)
                        return True
                    time.sleep(0.5)

                self._log("[APP ERROR] Timed out waiting for llama-server health response.")
                print("[APP ERROR] Timed out waiting for llama-server health response.", flush=True)
                self.stop()
                return False

            except Exception as e:
                self._log(f"[APP ERROR] Failed to start llama-server: {e}")
                print(f"[APP ERROR] Failed to start llama-server: {e}", flush=True)
                return False

    def sleep(self):
        """
        Puts the server to sleep: terminates the process and frees all VRAM,
        dropping GPU power draw from 330W to ~18W idle.
        """
        with self._lock:
            if self.process is not None:
                pid = self.process.pid
                self._log(f"[APP POWER SAVER] Putting GPU to sleep: Terminating PID {pid} and freeing VRAM.")
                print(f"[APP POWER SAVER] Putting GPU to sleep: Terminating PID {pid} and freeing VRAM.", flush=True)
                try:
                    if sys.platform == "win32":
                        subprocess.run(
                            ["taskkill", "/F", "/T", "/PID", str(pid)],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL
                        )
                    else:
                        self.process.terminate()
                        self.process.wait(timeout=3)
                except Exception as e:
                    print(f"[APP ERROR] Error terminating PID {pid}: {e}", flush=True)
                finally:
                    self.process = None
                    print("[APP STATUS] GPU is now sleeping (~18W idle).", flush=True)

    def stop(self):
        """Stops the running server instance."""
        self.sleep()

    def ensure_awake(self) -> bool:
        """
        Ensures the server is loaded and running. If sleeping, automatically boots it up.
        """
        if self.is_running:
            self.mark_activity()
            return True

        if not self.current_model_path:
            # Auto-resolve default model from config.yaml or scan directory
            from .model_scanner import ModelScanner
            scanner = ModelScanner()
            models = scanner.scan_models()
            cfg_default = "Qwen3.8-27B-UD-IQ4_XS.gguf"
            if CONFIG_PATH.is_file():
                try:
                    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                        cfg = yaml.safe_load(f) or {}
                        cfg_default = cfg.get("default_model", cfg_default)
                except Exception:
                    pass

            matched = None
            for m in models:
                if m.get("filename") == cfg_default or cfg_default.lower() in m.get("filename", "").lower():
                    matched = m.get("path")
                    break
            if not matched and models:
                matched = models[0].get("path")

            if matched:
                self.current_model_path = matched
                if self.current_params is None:
                    self.current_params = LlamaServerParams(
                        ctx_size=32768,
                        n_gpu_layers=99,
                        device="ROCm0",
                        flash_attn=True,
                        cache_type_k="q4_1",
                        cache_type_v="q4_1",
                        batch_size=2048,
                        ubatch_size=1024
                    )
            else:
                self._log("[APP ERROR] Cannot auto-wake: No models found in Models directory.")
                print("[APP ERROR] Cannot auto-wake: No models found in Models directory.", flush=True)
                return False

        self._log("[APP POWER WAKE] Auto-waking GPU for incoming task...")
        print("[APP POWER WAKE] Auto-waking GPU for incoming task...", flush=True)
        return self.start(self.current_model_path, self.current_params)

    def _idle_watchdog_loop(self):
        """Background thread monitoring idle time to automatically trigger sleep."""
        while self._watchdog_running:
            time.sleep(5)
            if self.auto_sleep_enabled and self.is_running:
                # If an active request is in flight or llama-server is processing tokens, reset timer
                if self.is_computing():
                    self.last_activity_time = time.time()
                    continue

                idle_duration = time.time() - self.last_activity_time
                if idle_duration >= self.idle_timeout_seconds:
                    print(f"[APP WATCHDOG] Idle timeout reached ({self.idle_timeout_seconds}s). Putting GPU to sleep.", flush=True)
                    self.sleep()

    def _log(self, message: str):
        self.logs.append(message)
        if len(self.logs) > self._max_log_lines:
            self.logs.pop(0)
