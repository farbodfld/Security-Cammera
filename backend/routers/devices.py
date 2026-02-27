import secrets
import string
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from schemas import *
from models import *
from security import *
from database import *
import schemas, models, security, database

router = APIRouter(tags=["devices"])

def generate_pair_code(length=6):
    characters = string.ascii_uppercase + string.digits
    return "SC-" + "".join(secrets.choice(characters) for _ in range(length))

def generate_device_token(length=32):
    characters = string.ascii_letters + string.digits
    return "".join(secrets.choice(characters) for _ in range(length))

def get_device_by_token(x_device_token: str = Header(...), db: Session = Depends(database.get_db)):
    if not x_device_token:
        raise HTTPException(status_code=401, detail="Missing X-Device-Token")
    device = db.query(models.Device).filter(models.Device.device_token == x_device_token).first()
    if not device:
        raise HTTPException(status_code=401, detail="Invalid X-Device-Token")
    return device


@router.post("/pair-codes", response_model=schemas.PairCodeResponse)
def create_pair_code(current_user: models.User = Depends(security.get_current_user), db: Session = Depends(database.get_db)):
    # Invalidate older unused pair codes for this user (optional clean up)
    db.query(models.PairCode).filter(models.PairCode.user_id == current_user.id, models.PairCode.used == False).delete()
    
    expires_delta = timedelta(minutes=10)
    expires_at = datetime.now(timezone.utc) + expires_delta
    code = generate_pair_code()
    
    db_pair_code = models.PairCode(
        pair_code=code,
        user_id=current_user.id,
        expires_at=expires_at
    )
    db.add(db_pair_code)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error generating pair code. Please try again.")
    
    return {"pair_code": code, "expires_in": 600}

@router.post("/devices/pair", response_model=schemas.DevicePairResponse)
def pair_device(pair_request: schemas.DevicePairRequest, db: Session = Depends(database.get_db)):
    # find pair code
    pair_code_entry = db.query(models.PairCode).filter(
        models.PairCode.pair_code == pair_request.pair_code,
        models.PairCode.used == False
    ).with_for_update().first() # atomically lock row

    if not pair_code_entry:
        raise HTTPException(status_code=400, detail="Invalid or expired pair code")
    
    if datetime.now(timezone.utc) > pair_code_entry.expires_at.replace(tzinfo=timezone.utc):
        raise HTTPException(status_code=400, detail="Pair code has expired")

    # Success: atomic swap
    pair_code_entry.used = True
    
    # Create device
    new_token = generate_device_token()
    device = models.Device(
        device_token=new_token,
        user_id=pair_code_entry.user_id,
        name=pair_request.device_name,
        platform=pair_request.platform,
        agent_version=pair_request.agent_version
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    
    return {"device_token": new_token, "device_id": device.id}
