"""
dashboard.py — Dashboard device management endpoints.

Requires JWT bearer token.
Pushes WS set_state to the agent when armed state changes.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from schemas import *
from models import *
from security import *
from database import *
import schemas, models, security, database

router = APIRouter(tags=["dashboard"])


async def _push_state(device_id: int, armed: bool) -> None:
    from routers.ws import manager
    await manager.push(device_id, {"type": "set_state", "armed": armed})


async def _push_config(device_id: int, cfg: dict) -> None:
    from routers.ws import manager
    await manager.push(device_id, {"type": "set_config", "config": cfg})


# ── GET /devices ──────────────────────────────────────────────────────────────

@router.get("/devices", response_model=list[schemas.DeviceResponse])
def get_devices(
    current_user: models.User = Depends(security.get_current_user),
    db: Session = Depends(database.get_db),
):
    devices = db.query(models.Device).filter(models.Device.user_id == current_user.id).all()
    out = []
    now = datetime.now(timezone.utc)
    for d in devices:
        d_dict = schemas.DeviceResponse.model_validate(d).model_dump()
        if d.last_seen_at:
            # Using 10 seconds as the offline threshold (agent heartbeats every 3s)
            d_dict['online'] = (now - d.last_seen_at.replace(tzinfo=timezone.utc)).total_seconds() < 10
        else:
            d_dict['online'] = False
        out.append(d_dict)
    return out


# ── PATCH /dashboard/devices/{id} ────────────────────────────────────────────

@router.patch("/dashboard/devices/{device_id}", response_model=schemas.DeviceResponse)
async def update_device(
    device_id: int,
    update_data: schemas.DeviceUpdateRequest,
    current_user: models.User = Depends(security.get_current_user),
    db: Session = Depends(database.get_db),
):
    device = (
        db.query(models.Device)
        .filter(models.Device.id == device_id, models.Device.user_id == current_user.id)
        .first()
    )
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    push_state  = False
    push_config = False

    if update_data.name is not None:
        device.name = update_data.name

    if update_data.headless is not None:
        device.headless = update_data.headless

    if update_data.armed is not None:
        if device.control_mode == models.ControlMode.TELEGRAM_ONLY.value:
            raise HTTPException(
                status_code=403,
                detail="Control mode is TELEGRAM_ONLY — use Telegram to arm/disarm."
            )
        device.armed = update_data.armed
        push_state = True

        # If arming, and it's currently offline, spawn the agent process remotely
        if device.armed:
            now_utc = datetime.now(timezone.utc)
            is_online = False
            if device.last_seen_at:
                is_online = (now_utc - device.last_seen_at.replace(tzinfo=timezone.utc)).total_seconds() < 10
            
            if not is_online:
                import subprocess, os, sys
                try:
                    agent_dir = os.path.abspath(os.path.join(os.getcwd(), "..", "agent"))
                    script_path = os.path.join(agent_dir, "src", "main.py")
                    
                    # We use sys.executable (which is the current backend venv python)
                    # because it turns out that's where the agent packages are installed.
                    cmd = [sys.executable, script_path]
                    if device.headless:
                        cmd.append("--headless")
                        
                    # 0x08000000 = CREATE_NO_WINDOW (This hides the console window)
                    creationflags = 0x08000000 if os.name == 'nt' else 0
                    
                    # Redirect streams to DEVNULL and close_fds to ensure a clean background start
                    subprocess.Popen(
                        cmd, 
                        cwd=agent_dir, 
                        creationflags=creationflags,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        close_fds=True
                    )
                except Exception as e:
                    print(f"Failed to spawn agent remotely: {e}")

    if update_data.confidence_threshold is not None:
        device.confidence_threshold = update_data.confidence_threshold
        push_config = True

    if update_data.snapshot_enabled is not None:
        device.snapshot_enabled = update_data.snapshot_enabled
        push_config = True

    if update_data.cooldown_sec is not None:
        device.cooldown_sec = update_data.cooldown_sec
        push_config = True

    if update_data.control_mode is not None:
        device.control_mode = update_data.control_mode.value

    db.commit()
    db.refresh(device)

    # Push changes to agent over WebSocket (if connected)
    if push_state:
        await _push_state(device.id, device.armed)

    if push_config:
        await _push_config(device.id, {
            "confidence_threshold": device.confidence_threshold,
            "snapshot_enabled":    device.snapshot_enabled,
            "cooldown_sec":        device.cooldown_sec,
        })

    # Return with computed online status
    now = datetime.now(timezone.utc)
    d_dict = schemas.DeviceResponse.model_validate(device).model_dump()
    if device.last_seen_at:
        d_dict['online'] = (now - device.last_seen_at.replace(tzinfo=timezone.utc)).total_seconds() < 10
    else:
        d_dict['online'] = False
        
    return d_dict
