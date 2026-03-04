"""
events.py — Event creation, snapshot upload, retrieval, and media serving.

After creating an event / uploading snapshot, fires a Telegram alert
to the device owner (if linked).
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import os, uuid, shutil

from schemas import *
from models import *
from security import *
from database import *
from routers.devices import get_device_by_token
import schemas, models, security, database

router = APIRouter(tags=["events"])

MEDIA_DIR = os.environ.get("MEDIA_DIR", "./media")
os.makedirs(MEDIA_DIR, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# POST /events
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/events", response_model=schemas.EventCreateResponse, status_code=201)
async def create_event(
    event_data: schemas.EventCreateRequest,
    background_tasks: BackgroundTasks,
    device: models.Device = Depends(get_device_by_token),
    db: Session = Depends(database.get_db),
):
    event_id = str(uuid.uuid4())

    new_event = models.Event(
        id         = event_id,
        device_id  = device.id,
        user_id    = device.user_id,
        confidence = event_data.confidence,
        happened_at= event_data.happened_at,
        created_at = datetime.now(timezone.utc),
    )

    db.add(new_event)
    db.commit()

    # Fire Telegram alert in background (no snapshot yet)
    background_tasks.add_task(
        _tg_event_alert,
        user_id    = device.user_id,
        device_name= device.name or f"Device #{device.id}",
        confidence = event_data.confidence,
        happened_at= event_data.happened_at,
        snap_url   = None,
        db_url     = str(db.get_bind().url),
    )

    return {"id": event_id}


# ─────────────────────────────────────────────────────────────────────────────
# POST /events/{event_id}/snapshot
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/events/{event_id}/snapshot", response_model=schemas.SnapshotUploadResponse)
def upload_snapshot(
    event_id: str,
    file: UploadFile = File(...),
    device: models.Device = Depends(get_device_by_token),
    db: Session = Depends(database.get_db),
):
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.device_id != device.id:
        raise HTTPException(status_code=403, detail="Forbidden: event does not belong to this device")

    # Secure, deterministic storage path
    target_dir = os.path.join(MEDIA_DIR, "events")
    os.makedirs(target_dir, exist_ok=True)

    filename  = f"{event_id}.jpg"   # UUID filename — no traversal possible
    file_path = os.path.join(target_dir, filename)

    with open(file_path, "wb") as buf:
        shutil.copyfileobj(file.file, buf)

    event.image_filename = filename
    db.commit()

    return {"success": True, "image_url": f"/media/events/{filename}"}


# ─────────────────────────────────────────────────────────────────────────────
# GET /events
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/events", response_model=list[schemas.EventResponse])
def get_events(
    device_id: int | None = None,
    limit:  int = 50,
    skip:   int = 0,
    current_user: models.User = Depends(security.get_current_user),
    db: Session = Depends(database.get_db),
):
    q = db.query(models.Event).filter(models.Event.user_id == current_user.id)
    if device_id:
        q = q.filter(models.Event.device_id == device_id)
    events = q.order_by(models.Event.happened_at.desc()).offset(skip).limit(limit).all()
    return events


# ─────────────────────────────────────────────────────────────────────────────
# DELETE /events
# ─────────────────────────────────────────────────────────────────────────────

@router.delete("/events")
def delete_all_events(
    current_user: models.User = Depends(security.get_current_user),
    db: Session = Depends(database.get_db),
):
    events = db.query(models.Event).filter(models.Event.user_id == current_user.id).all()
    
    deleted_count = 0
    for ev in events:
        if ev.image_filename:
            file_path = os.path.join(MEDIA_DIR, "events", ev.image_filename)
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                print(f"Failed to delete {file_path}: {e}")
        
        db.delete(ev)
        deleted_count += 1
        
    db.commit()
    return {"success": True, "deleted": deleted_count}


# ─────────────────────────────────────────────────────────────────────────────
# Background task — send Telegram alert (runs after response is sent)
# ─────────────────────────────────────────────────────────────────────────────

def _tg_event_alert(
    user_id: int,
    device_name: str,
    confidence: float,
    happened_at: datetime,
    snap_url: str | None,
    db_url: str,
) -> None:
    """
    Called as a FastAPI BackgroundTask.  Opens its own short-lived DB session
    so it doesn't conflict with the request session that's already been closed.
    """
    import asyncio
    from database import SessionLocal
    from routers.telegram import send_event_alert

    db2 = SessionLocal()
    try:
        asyncio.run(send_event_alert(
            user_id     = user_id,
            device_name = device_name,
            confidence  = confidence,
            happened_at = happened_at,
            snapshot_url= snap_url,
            db          = db2,
        ))
    finally:
        db2.close()
