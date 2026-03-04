"""
ws.py — WebSocket endpoint for agent connections.

Auth: device_token is sent as HTTP header X-Device-Token.
Flow: connect → receive hello → send init → heartbeat loop
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Header
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import json
import logging

from models import *
from database import *
import models, database

router = APIRouter()
logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages active WebSocket connections keyed by device_id."""

    def __init__(self):
        self.active: dict[int, WebSocket] = {}

    async def connect(self, websocket: WebSocket, device_id: int):
        self.active[device_id] = websocket
        logger.info(f"Device {device_id} connected via WS")

    def disconnect(self, device_id: int):
        self.active.pop(device_id, None)
        logger.info(f"Device {device_id} disconnected from WS")

    async def push(self, device_id: int, payload: dict) -> bool:
        """Push a JSON message to a connected device. Returns True on success."""
        ws = self.active.get(device_id)
        if not ws:
            return False
        try:
            await ws.send_json(payload)
            return True
        except Exception as e:
            logger.warning(f"WS push to device {device_id} failed: {e}")
            self.disconnect(device_id)
            return False


# Singleton shared across imports (telegram.py imports this)
manager = ConnectionManager()


@router.websocket("/ws/agent")
async def websocket_endpoint(websocket: WebSocket):
    """
    Agent WebSocket endpoint.

    Auth: device sends X-Device-Token header at connection time.
    Protocol:
      agent → server: { "type": "hello" }
      server → agent: { "type": "init", "armed": bool, "config": {...} }
      agent → server: { "type": "heartbeat" }  (every 20s)
      server → agent: { "type": "heartbeat_ack" }
      server → agent: { "type": "set_state", "armed": bool }
      server → agent: { "type": "set_config", "config": {...} }
    """
    # ── Read device token from header ─────────────────────────────────────
    device_token = websocket.headers.get("x-device-token")
    if not device_token:
        await websocket.close(code=4001, reason="Missing X-Device-Token header")
        return

    # ── Open a fresh DB session for this connection ───────────────────────
    db: Session = next(database.get_db())
    device_id: int | None = None

    try:
        device = db.query(models.Device).filter(
            models.Device.device_token == device_token
        ).first()

        if not device:
            await websocket.close(code=4003, reason="Invalid device token")
            return

        device_id = device.id
        await websocket.accept()
        await manager.connect(websocket, device_id)

        # ── Send init ─────────────────────────────────────────────────────
        device.armed = True
        init_payload = {
            "type": "init",
            "armed": device.armed,
            "config": {
                "confidence_threshold": device.confidence_threshold,
                "snapshot_enabled":    device.snapshot_enabled,
                "cooldown_sec":        device.cooldown_sec,
                "control_mode":        device.control_mode,
            },
        }
        await websocket.send_json(init_payload)

        # ── Update last_seen ──────────────────────────────────────────────
        device.last_seen_at = datetime.now(timezone.utc)
        db.commit()

        # ── Heartbeat loop ────────────────────────────────────────────────
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)

            if msg.get("type") == "heartbeat":
                device = db.query(models.Device).filter(
                    models.Device.id == device_id
                ).first()
                if device:
                    device.last_seen_at = datetime.now(timezone.utc)
                    db.commit()
                await websocket.send_json({"type": "heartbeat_ack"})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WS error for device {device_id}: {e}")
    finally:
        if device_id:
            manager.disconnect(device_id)
            # Auto-disarm on disconnect
            try:
                db_cleanup = next(database.get_db())
                dev = db_cleanup.query(models.Device).filter(models.Device.id == device_id).first()
                if dev:
                    dev.armed = False
                    db_cleanup.commit()
                db_cleanup.close()
            except Exception as e:
                logger.error(f"Failed to auto-disarm device {device_id}: {e}")
        db.close()
