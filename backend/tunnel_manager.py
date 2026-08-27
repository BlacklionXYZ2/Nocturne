"""
Nocturne Mobile Companion & Cloudflare Quick Tunnel Manager
===========================================================
Spawns a zero-config Cloudflare Tunnel (`trycloudflare.com`) to allow
remote monitoring and interaction from a mobile phone over HTTPS/WSS
with cryptographic session token protection and QR code generation.
"""

import os
import sys
import re
import time
import secrets
import threading
import subprocess
from typing import Optional, Dict, Any


class CloudflareTunnelManager:
    """Manages the lifecycle of a secure Cloudflare quick tunnel for mobile pairing."""

    def __init__(self, local_port: int = 5000):
        self.local_port = local_port
        self.process: Optional[subprocess.Popen] = None
        self.tunnel_url: Optional[str] = None
        self.auth_token: str = secrets.token_hex(16)
        self.is_active: bool = False
        self._lock = threading.RLock()
        self.error_message: Optional[str] = None

    @property
    def authenticated_url(self) -> Optional[str]:
        """Returns the public HTTPS URL with embedded session auth token."""
        if not self.tunnel_url:
            return None
        return f"{self.tunnel_url}?auth={self.auth_token}"

    def get_status(self) -> Dict[str, Any]:
        """Returns current tunnel connection state and URLs."""
        return {
            "is_active": self.is_active,
            "tunnel_url": self.tunnel_url,
            "authenticated_url": self.authenticated_url,
            "auth_token": self.auth_token,
            "error": self.error_message
        }

    def start(self, timeout_seconds: int = 25) -> bool:
        """Spawns the Cloudflare tunnel process and extracts the assigned public URL."""
        with self._lock:
            if self.is_active and self.tunnel_url:
                return True

            self.stop()
            self.error_message = None
            self.auth_token = secrets.token_hex(16)

            # Determine best command available (npx untun or cloudflared)
            cmd = ["npx", "-y", "cloudflared", "tunnel", "--url", f"http://127.0.0.1:{self.local_port}"]

            print(f"[Nocturne Tunnel] Spawning Cloudflare Quick Tunnel for port {self.local_port}...", flush=True)

            try:
                creation_flags = 0
                if sys.platform == "win32":
                    creation_flags = subprocess.CREATE_NO_WINDOW

                self.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    shell=(sys.platform == "win32"),
                    creationflags=creation_flags
                )

                start_time = time.time()
                url_pattern = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")

                while time.time() - start_time < timeout_seconds:
                    if self.process.poll() is not None:
                        self.error_message = f"Process exited with code {self.process.returncode}"
                        return False

                    line = self.process.stdout.readline() if self.process.stdout else ""
                    if line:
                        clean = line.strip()
                        match = url_pattern.search(clean)
                        if match:
                            self.tunnel_url = match.group(0)
                            self.is_active = True
                            print(f"[Nocturne Tunnel] Connected! Public Mobile URL: {self.authenticated_url}", flush=True)
                            return True

                    time.sleep(0.3)

                self.error_message = "Timed out waiting for Cloudflare Tunnel URL."
                self.stop()
                return False

            except Exception as e:
                self.error_message = str(e)
                print(f"[Nocturne Tunnel] Failed to start: {e}", flush=True)
                return False

    def stop(self):
        """Terminates the Cloudflare tunnel process."""
        with self._lock:
            if self.process is not None:
                print("[Nocturne Tunnel] Stopping Cloudflare tunnel...", flush=True)
                try:
                    self.process.terminate()
                    self.process.wait(timeout=3)
                except Exception:
                    try:
                        self.process.kill()
                    except Exception:
                        pass
                finally:
                    self.process = None
                    self.tunnel_url = None
                    self.is_active = False


# Global singleton instance
tunnel_mgr = CloudflareTunnelManager(local_port=5000)
