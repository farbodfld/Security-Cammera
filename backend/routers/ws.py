from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
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
    def __init__(self):
        # Maps device_id -> WebSocket
        self.active_connections: dict[int, WebSocket] = {}

    async def connect(self, websocket: WebSocket, device_id: int):
        await websocket.accept()
        self.active_connections[device_id] = websocket
        logger.info(f"Device {device_id} connected via WS")

    def disconnect(self, device_id: int):
        if device_id in self.active_connections:
            del self.active_connections[device_id]
            logger.info(f"Device {device_id} disconnected from WS")

    async def send_personal_message(self, message: dict, device_id: int):
        if device_id in self.active_connections:
            ws = self.active_connections[device_id]
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.error(f"Failed to send mesage to {device_id}: {e}")

manager = ConnectionManager()


@router.websocket("/ws/agent")
async def websocket_endpoint(websocket: WebSocket, db: Session = Depends(database.get_db)):
    await websocket.accept()
    device_id = None
    
    try:
        # Require 'hello' message first
        data = await websocket.receive_text()
        message = json.loads(data)
        
        if message.get("type") != "hello" or not message.get("device_token"):
            await websocket.close(code=4001, reason="Invalid auth sequence")
            return
            
        device_token = message.get("device_token")
        device = db.query(models.Device).filter(models.Device.device_token == device_token).first()
        
        if not device:
            await websocket.close(code=4001, reason="Invalid token")
            return
            
        device_id = device.id
        manager.active_connections[device_id] = websocket
        
        # Send initial sync payload per specification
        init_payload = {
            "type": "init",
            "armed": device.armed,
            "threshold": device.threshold,
            "cooldown_sec": device.cooldown_sec,
            "control_mode": device.control_mode
        }
        await websocket.send_json(init_payload)
        
        # Update last seen
        device.last_seen_at = datetime.now(timezone.utc)
        db.commit()

        # Enter Heartbeat loop
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            
            if msg.get("type") == "heartbeat":
                # refresh device from db context if needed
                device = db.query(models.Device).filter(models.Device.id == device_id).first()
                if device:
                    device.last_seen_at = datetime.now(timezone.utc)
                    db.commit()
                await websocket.send_json({"type": "heartbeat_ack"})
                
    except WebSocketDisconnect:
        if device_id:
            manager.disconnect(device_id)
    except Exception as e:
        logger.error(f"WS error: {e}")
        if device_id:
            manager.disconnect(device_id)
        await websocket.close()
