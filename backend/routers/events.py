from fastapi import APIRouter, Depends, HTTPException, Header, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import os, uuid
import shutil

from schemas import *
from models import *
from security import *
from database import *
from routers.devices import get_device_by_token
import schemas, models, security, database

router = APIRouter(tags=["events"])

MEDIA_DIR = os.environ.get("MEDIA_DIR", "./media")
os.makedirs(MEDIA_DIR, exist_ok=True)

@router.post("/events", response_model=schemas.EventCreateResponse)
def create_event(
    event_data: schemas.EventCreateRequest,
    device: models.Device = Depends(get_device_by_token),
    db: Session = Depends(database.get_db)
):
    event_id = str(uuid.uuid4())
    
    new_event = models.Event(
        id=event_id,
        device_id=device.id,
        user_id=device.user_id,
        event_type=event_data.event_type,
        confidence=event_data.confidence,
        happened_at=event_data.happened_at,
        created_at=datetime.now(timezone.utc)
    )
    
    db.add(new_event)
    db.commit()
    
    return {"event_id": event_id}

@router.post("/events/{event_id}/snapshot", response_model=schemas.SnapshotUploadResponse)
def upload_snapshot(
    event_id: str,
    file: UploadFile = File(...),
    device: models.Device = Depends(get_device_by_token),
    db: Session = Depends(database.get_db)
):
    # Strict validation mapping device token to event ownership
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
        
    if event.device_id != device.id:
        raise HTTPException(status_code=403, detail="Forbidden: Event does not belong to this device")
        
    # Build secure deterministic output path
    # media/user_<user_id>/device_<device_id>/
    user_dir = f"user_{device.user_id}"
    device_dir = f"device_{device.id}"
    target_dir = os.path.join(MEDIA_DIR, user_dir, device_dir)
    os.makedirs(target_dir, exist_ok=True)
    
    filename = f"{event_id}.jpg" # safe UUID filename to prevent traversal
    file_path = os.path.join(target_dir, filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    event.image_filename = filename
    db.commit()
    
    # Exposing safe proxy url, not real path
    return {"success": True, "image_url": f"/media/events/{event_id}.jpg"}

@router.get("/events", response_model=list[schemas.EventResponse])
def get_events(
    device_id: int = None,
    limit: int = 50,
    offset: int = 0,
    current_user: models.User = Depends(security.get_current_user),
    db: Session = Depends(database.get_db)
):
    query = db.query(models.Event).filter(models.Event.user_id == current_user.id)
    if device_id:
        query = query.filter(models.Event.device_id == device_id)
        
    events = query.order_by(models.Event.happened_at.desc()).offset(offset).limit(limit).all()
    
    # Format URLs properly if an image filename is preserved
    response_events = []
    for event in events:
        er = schemas.EventResponse.model_validate(event)
        if event.image_filename:
            er.image_url = f"/media/events/{event.image_filename}"
        response_events.append(er)
        
    return response_events

@router.get("/media/events/{filename}")
def serve_media(
    filename: str,
    current_user: models.User = Depends(security.get_current_user),
    db: Session = Depends(database.get_db)
):
    # Prevent traversal
    safe_filename = os.path.basename(filename)
    
    # Filename mapped to event UUID
    event_id = safe_filename.replace(".jpg", "")
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    
    if not event:
        raise HTTPException(status_code=404, detail="Image not found")
    
    # Verify user ownership
    if event.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
        
    user_dir = f"user_{event.user_id}"
    device_dir = f"device_{event.device_id}"
    file_path = os.path.join(MEDIA_DIR, user_dir, device_dir, safe_filename)
    
    if not os.path.exists(file_path):
         raise HTTPException(status_code=404, detail="File on disk not found")
         
    return FileResponse(file_path)
