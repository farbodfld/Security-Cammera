import os
import random
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.orm import Session
import httpx
import logging

from schemas import *
from models import *
from security import *
from database import *
import schemas, models, security, database

router = APIRouter(prefix="/telegram", tags=["telegram"])
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

def generate_otp():
    return str(random.randint(100000, 999999))

async def send_telegram_message(chat_id: str, text: str):
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN not set, skipping message")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    async with httpx.AsyncClient() as client:
        await client.post(url, json={"chat_id": chat_id, "text": text})

@router.post("/webhook")
async def telegram_webhook(request: Request, db: Session = Depends(database.get_db)):
    data = await request.json()
    logger.info(f"Received telegram update: {data}")
    
    update_id = data.get("update_id")
    if not update_id:
        return {"status": "ignored"}
        
    # Idempotency check 
    existing = db.query(models.TelegramUpdate).filter(models.TelegramUpdate.update_id == update_id).first()
    if existing:
        return {"status": "already_processed"}
        
    # Insert new update record 
    db.add(models.TelegramUpdate(update_id=update_id))
    
    if "message" in data:
        message = data["message"]
        chat_id = str(message["chat"]["id"])
        text = message.get("text", "")
        
        if text.startswith("/start"):
            # Generate OTP 
            otp = generate_otp()
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
            
            db.add(models.TelegramOTP(
                otp_code=otp,
                chat_id=chat_id,
                expires_at=expires_at
            ))
            
            await send_telegram_message(
                chat_id, 
                f"Welcome to Security Camera Agent!\n\nYour OTP is: {otp}\n\nEnter this in your dashboard to link this chat. Expires in 5 minutes."
            )
            
        elif text.startswith("/devices"):
            link = db.query(models.TelegramLink).filter(models.TelegramLink.chat_id == chat_id, models.TelegramLink.enabled == True).first()
            if not link:
                await send_telegram_message(chat_id, "Please link your account first via the dashboard.")
            else:
                devices = db.query(models.Device).filter(models.Device.user_id == link.user_id).all()
                if not devices:
                    await send_telegram_message(chat_id, "No devices found.")
                else:
                    msg_lines = ["Your Devices:"]
                    for d in devices:
                        status = "🟢 ARM" if d.armed else "🔴 DISARM"
                        msg_lines.append(f"[{d.id}] {d.name or 'Unknown'} - Status: {status}")
                    await send_telegram_message(chat_id, "\n".join(msg_lines))
                    
        elif text.startswith("/arm") or text.startswith("/disarm"):
            action_is_arm = text.startswith("/arm")
            parts = text.split()
            link = db.query(models.TelegramLink).filter(models.TelegramLink.chat_id == chat_id, models.TelegramLink.enabled == True).first()
            
            if not link:
                await send_telegram_message(chat_id, "Please link your account first via the dashboard.")
            else:
                user_devices = db.query(models.Device).filter(models.Device.user_id == link.user_id).all()
                if not user_devices:
                    await send_telegram_message(chat_id, "No devices found.")
                else:
                    target_device = None
                    if len(user_devices) == 1:
                        target_device = user_devices[0]
                    else:
                        if len(parts) > 1 and parts[1].isdigit():
                            req_id = int(parts[1])
                            target_device = next((d for d in user_devices if d.id == req_id), None)
                        if not target_device:
                            await send_telegram_message(chat_id, "You have multiple devices. Please specify the ID. Example: /arm 2")
                    
                    if target_device:
                        if target_device.control_mode == models.ControlMode.DASHBOARD_ONLY.value:
                            await send_telegram_message(chat_id, f"Device [{target_device.id}] rejects Telegram controls. Only Dashboard is allowed.")
                        else:
                            target_device.armed = action_is_arm
                            # Note: WS push is needed here later!
                            state_str = "ARMED" if action_is_arm else "DISARMED"
                            await send_telegram_message(chat_id, f"Device [{target_device.id}] ({target_device.name}) is now {state_str}.")

    db.commit()
    return {"status": "ok"}

@router.post("/verify-otp", response_model=schemas.OTPVerifyResponse)
def verify_otp(
    payload: schemas.OTPVerifyRequest, 
    current_user: models.User = Depends(security.get_current_user), 
    db: Session = Depends(database.get_db)
):
    otp_record = db.query(models.TelegramOTP).filter(
        models.TelegramOTP.otp_code == payload.otp_code,
        models.TelegramOTP.used == False
    ).first()
    
    if not otp_record or datetime.now(timezone.utc) > otp_record.expires_at.replace(tzinfo=timezone.utc):
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")
        
    otp_record.used = True
    
    # Check if user already has a link 
    existing_link = db.query(models.TelegramLink).filter(models.TelegramLink.user_id == current_user.id).first()
    if existing_link:
        existing_link.chat_id = otp_record.chat_id
        existing_link.enabled = True
    else:
        new_link = models.TelegramLink(
            user_id=current_user.id,
            chat_id=otp_record.chat_id,
            enabled=True
        )
        db.add(new_link)
        
    db.commit()
    return {"success": True, "chat_id": otp_record.chat_id}
