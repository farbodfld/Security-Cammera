"""
api_client.py — HTTP and WebSocket client for the Security Camera backend.

Handles:
  • Device pairing (POST /devices/pair)
  • Posting detection events (POST /events)
  • Uploading snapshots  (POST /events/{id}/snapshot)
  • WebSocket connection (ws://.../ws/agent) with:
      - hello   → receives init (armed state + config)
      - heartbeat every 20s
      - set_state / set_config messages from server
"""

import json
import platform
import threading
import time
import logging
import requests
import websocket
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional, Tuple

logger = logging.getLogger("api_client")


class APIClient:
    """
    Thread-safe HTTP client for the backend REST API.
    The WebSocket connection runs on a separate daemon thread.
    """

    HEARTBEAT_INTERVAL = 3          # seconds between heartbeats
    RECONNECT_BASE     = 2           # seconds; doubles each failed attempt
    RECONNECT_MAX      = 60          # cap
    REQUEST_TIMEOUT    = 10          # seconds for HTTP calls

    def __init__(self, server_url: str):
        self.server_url  = server_url.rstrip("/")
        self._token: str | None = None

        # Shared state pushed by the backend via WebSocket
        self.armed: bool = True
        self.confidence_threshold: float | None = None  # None = use local config
        self.snapshot_enabled: bool = True

        # Callbacks registered outside (e.g. by EventHandler)
        self._on_armed_change: Optional[Callable[[bool], None]] = None
        self._on_config_change: Optional[Callable[[dict], None]] = None

        # WS housekeeping
        self._ws_thread: threading.Thread | None = None
        self._ws_stop   = threading.Event()

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    def set_token(self, token: str) -> None:
        """Set the device token used for all authenticated requests."""
        self._token = token

    def pair_device(
        self, pair_code: str, device_name: str = "My Camera"
    ) -> tuple[bool, str | None, str]:
        """
        Call POST /devices/pair with the given pair_code.

        Returns a 3-tuple:
          (True,  device_token, "")             on success
          (False, None,         detail_string)   on failure

        detail_string values:
          "PAIR_CODE_INVALID" — code not found
          "PAIR_CODE_EXPIRED" — code past expiry
          "network"           — connection / timeout error
          "SERVER_ERROR"      — unexpected backend response
        """
        url = f"{self.server_url}/devices/pair"
        payload = {
            "pair_code": pair_code,
            "device_name": device_name,
            "platform": platform.system(),   # "Windows" / "Darwin" / "Linux"
            "agent_version": "1.1.0",
        }
        try:
            resp = requests.post(
                url,
                json=payload,
                timeout=self.REQUEST_TIMEOUT,
            )
            if resp.status_code in (200, 201):
                token = resp.json().get("device_token")
                return (True, token, "")
            else:
                # Backend returns a detail string in the JSON body
                detail = "SERVER_ERROR"
                try:
                    detail = resp.json().get("detail", "SERVER_ERROR")
                except Exception:
                    pass
                logger.error("Pair failed [%d]: %s", resp.status_code, resp.text)
                return (False, None, detail)
        except requests.Timeout:
            logger.error("Pair request timed out")
            return (False, None, "network")
        except requests.ConnectionError as e:
            logger.error("Pair connection error: %s", e)
            return (False, None, "network")
        except requests.RequestException as e:
            logger.error("Pair request error: %s", e)
            return (False, None, "network")

    def post_event(self, confidence: float, happened_at: datetime) -> int | None:
        """
        POST /events to report a detection event.
        Returns the event_id on success, or None on failure.
        """
        if not self._token:
            return None
        url = f"{self.server_url}/events"
        payload = {
            "confidence": float(f"{confidence:.4f}"),
            "happened_at": happened_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        try:
            resp = requests.post(
                url,
                json=payload,
                headers={"X-Device-Token": self._token},
                timeout=self.REQUEST_TIMEOUT,
            )
            if resp.status_code in (200, 201):
                return resp.json().get("id")
            else:
                logger.warning(f"post_event failed [{resp.status_code}]: {resp.text}")
                return None
        except requests.RequestException as e:
            logger.warning(f"post_event error: {e}")
            return None

    def upload_snapshot(self, event_id: int, image_path: str) -> bool:
        """
        POST /events/{event_id}/snapshot to attach a JPEG snapshot.
        Returns True on success.
        """
        if not self._token:
            return False
        url = f"{self.server_url}/events/{event_id}/snapshot"
        try:
            with open(image_path, "rb") as f:
                resp = requests.post(
                    url,
                    files={"file": ("snapshot.jpg", f, "image/jpeg")},
                    headers={"X-Device-Token": self._token},
                    timeout=self.REQUEST_TIMEOUT,
                )
            if resp.status_code in (200, 201):
                return True
            else:
                logger.warning(f"upload_snapshot failed [{resp.status_code}]: {resp.text}")
                return False
        except (requests.RequestException, OSError) as e:
            logger.warning(f"upload_snapshot error: {e}")
            return False

    def register_callbacks(self, on_armed_change=None, on_config_change=None):
        """Register callbacks for state/config changes received via WebSocket."""
        self._on_armed_change  = on_armed_change
        self._on_config_change = on_config_change

    # ──────────────────────────────────────────────────────────────────────────
    # WebSocket (runs in its own daemon thread)
    # ──────────────────────────────────────────────────────────────────────────

    def start_websocket(self) -> None:
        """Start the WebSocket connection in a background thread."""
        self._ws_stop.clear()
        t = threading.Thread(
            target=self._ws_loop, daemon=True, name="ws-agent"
        )
        self._ws_thread = t
        t.start()

    def stop_websocket(self) -> None:
        """Signal the WebSocket thread to terminate."""
        self._ws_stop.set()

    def _ws_loop(self) -> None:
        """Reconnect loop — retries with exponential backoff."""
        backoff = self.RECONNECT_BASE

        while not self._ws_stop.is_set():
            if not self._token:
                time.sleep(1)
                continue

            ws_url = self.server_url.replace("http://", "ws://").replace("https://", "wss://")
            ws_url = f"{ws_url}/ws/agent"

            try:
                logger.info(f"Connecting to WebSocket: {ws_url}")
                ws = websocket.WebSocketApp(
                    ws_url,
                    header={"X-Device-Token": self._token},
                    on_open=self._on_ws_open,
                    on_message=self._on_ws_message,
                    on_error=self._on_ws_error,
                    on_close=self._on_ws_close,
                )
                # run_forever blocks until disconnect
                ws.run_forever(ping_interval=0)  # type: ignore
                backoff = self.RECONNECT_BASE   # reset on clean close
            except Exception as e:
                logger.warning(f"WS error: {e}")

            if self._ws_stop.is_set():
                break

            logger.info(f"WS disconnected — reconnecting in {backoff}s …")
            time.sleep(backoff)
            backoff = min(backoff * 2, self.RECONNECT_MAX)

    def _on_ws_open(self, ws) -> None:
        """Send the hello handshake right after connection."""
        logger.info("WebSocket connected — sending hello")
        payload = json.dumps({"type": "hello"})
        ws.send(payload)

        # Start heartbeat thread
        def _heartbeat():
            while True:
                time.sleep(self.HEARTBEAT_INTERVAL)
                try:
                    ws.send(json.dumps({"type": "heartbeat"}))
                except Exception:
                    break

        t = threading.Thread(target=_heartbeat, daemon=True, name="ws-heartbeat")
        t.start()

    def _on_ws_message(self, ws, raw: str) -> None:
        """Handle an incoming message from the backend."""
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            return

        mtype = msg.get("type")

        if mtype == "init":
            # Backend sends current armed state + config after hello
            armed  = msg.get("armed", True)
            config = msg.get("config", {})
            self.armed = armed
            if config.get("confidence_threshold") is not None:
                self.confidence_threshold = config["confidence_threshold"]
            if config.get("snapshot_enabled") is not None:
                self.snapshot_enabled = config["snapshot_enabled"]
            logger.info(f"WS init: armed={armed}, config={config}")
            if self._on_armed_change:
                self._on_armed_change(armed)
            if self._on_config_change and config:
                self._on_config_change(config)

        elif mtype == "set_state":
            armed = msg.get("armed")
            if armed is not None:
                self.armed = armed
                logger.info(f"WS set_state: armed={armed}")
                if self._on_armed_change:
                    self._on_armed_change(armed)
                
                # Auto-quit if agent is disarmed remotely
                if not armed:
                    logger.info("Disarmed remotely via WebSocket. Shutting down agent...")
                    # Give logs time to flush
                    time.sleep(0.5)
                    import os
                    os._exit(0)

        elif mtype == "set_config":
            cfg = msg.get("config", {})
            if "confidence_threshold" in cfg:
                self.confidence_threshold = cfg["confidence_threshold"]
            if "snapshot_enabled" in cfg:
                self.snapshot_enabled = cfg["snapshot_enabled"]
            logger.info(f"WS set_config: {cfg}")
            if self._on_config_change:
                self._on_config_change(cfg)

    def _on_ws_error(self, ws, error) -> None:
        logger.warning(f"WS error: {error}")

    def _on_ws_close(self, ws, code, msg) -> None:
        logger.info(f"WS closed (code={code})")
