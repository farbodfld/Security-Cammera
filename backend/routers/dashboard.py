from fastapi import APIRouter, Depends, HTTPException, Header, UploadFile, File
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import os, uuid
import shutil

from schemas import *
from models import *
from security import *
from database import *
import schemas, models, security, database

router = APIRouter(tags=["devices"])

@router.get("/devices", response_model=list[schemas.DeviceResponse])
def get_devices(current_user: models.User = Depends(security.get_current_user), db: Session = Depends(database.get_db)):
    devices = db.query(models.Device).filter(models.Device.user_id == current_user.id).all()
    
    response_devices = []
    current_time = datetime.now(timezone.utc)
    for device in devices:
        last_seen = device.last_seen_at.replace(tzinfo=timezone.utc)
        is_online = (current_time - last_seen).total_seconds() <= 30
        
        device_resp = schemas.DeviceResponse.model_validate(device)
        device_resp.status = "online" if is_online else "offline"
        response_devices.append(device_resp)
        
    return response_devices

@router.patch("/devices/{device_id}", response_model=schemas.DeviceResponse)
def update_device(device_id: int, update_data: schemas.DeviceUpdateRequest, current_user: models.User = Depends(security.get_current_user), db: Session = Depends(database.get_db)):
    device = db.query(models.Device).filter(models.Device.id == device_id, models.Device.user_id == current_user.id).first()
    
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
        
    if update_data.armed is not None:
        if device.control_mode == models.ControlMode.TELEGRAM_ONLY.value:
            raise HTTPException(status_code=403, detail="Control mode is TELEGRAM_ONLY, cannot arm/disarm via dashboard")
        device.armed = update_data.armed
        
    if update_data.threshold is not None:
        device.threshold = update_data.threshold
    if update_data.cooldown_sec is not None:
        device.cooldown_sec = update_data.cooldown_sec
    if update_data.control_mode is not None:
        device.control_mode = update_data.control_mode.value
        
    db.commit()
    db.refresh(device)
    
    device_resp = schemas.DeviceResponse.model_validate(device)
    current_time = datetime.now(timezone.utc)
    last_seen = device.last_seen_at.replace(tzinfo=timezone.utc)
    device_resp.status = "online" if ((current_time - last_seen).total_seconds() <= 30) else "offline"
    return device_resp
