"""
telegram.py — Telegram bot integration.

Handles:
  • POST /telegram/webhook  — Telegram Bot API webhook (idempotent)
  • POST /telegram/otp      — Dashboard generates OTP for the user to link account
  • POST /telegram/verify-otp — Dashboard submits OTP code to complete linking

Bot commands handled in webhook:
  /start   → generate OTP, send to chat
  /devices → list user's devices
  /arm [n] → arm device (n = device index if multiple)
  /disarm [n] → disarm device

Alert sending:
  send_event_alert(user_id, device, confidence, snap_url) — called from events router
"""

import os
import secrets
import asyncio
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from fastapi import Request
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
_TG_API = "https://api.telegram.org/bot"

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _otp() -> str:
    """6-digit cryptographically random OTP."""
    return str(secrets.randbelow(900000) + 100000)


async def _send(chat_id: str, text: str, parse_mode: str = "HTML") -> None:
    """Fire-and-forget Telegram sendMessage."""
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN not set — skipping Telegram message")
        return
    url = f"{_TG_API}{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(url, json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode,
            })
    except Exception as e:
        logger.warning(f"Telegram sendMessage failed: {e}")


async def _push_arm_state(device: models.Device, armed: bool) -> None:
    """Push set_state to the agent over WebSocket (if connected)."""
    from routers.ws import manager   # import here to avoid circular at module load
    await manager.push(device.id, {"type": "set_state", "armed": armed})


# ─────────────────────────────────────────────────────────────────────────────
# Public helper — called by events router after a new event is created
# ─────────────────────────────────────────────────────────────────────────────

async def send_event_alert(
    user_id: int,
    device_name: str,
    confidence: float,
    happened_at: datetime,
    snapshot_url: str | None,
    db: Session,
) -> None:
    """Send a Telegram alert to the user linked to user_id (if any)."""
    link = (
        db.query(models.TelegramLink)
        .filter(
            models.TelegramLink.user_id == user_id,
            models.TelegramLink.enabled == True,
        )
        .first()
    )
    if not link:
        return

    ts = happened_at.strftime("%H:%M:%S UTC")
    icon = "🚨"
    msg = (
        f"{icon} <b>Person Detected</b>\n"
        f"📷 Device: <b>{device_name}</b>\n"
        f"🕐 Time: {ts}\n"
        f"🎯 Confidence: {round(confidence * 100)}%"
    )
    if snapshot_url:
        msg += f"\n🖼 <a href=\"{snapshot_url}\">View Snapshot</a>"

    await _send(link.chat_id, msg)


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard endpoint — generate OTP for the current user
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/otp")
def generate_otp_for_user(
    current_user: models.User = Depends(security.get_current_user),
    db: Session = Depends(database.get_db),
):
    """
    Dashboard calls this to get an OTP the user can send to the bot.
    The OTP is stored in the DB (not linked to a chat yet — that happens
    when the user sends /start and types the OTP, or uses /verify-otp endpoint).
    """
    otp_code  = _otp()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)

    db.add(models.TelegramOTP(
        otp_code   = otp_code,
        chat_id    = "",          # filled when user sends the OTP to the bot
        expires_at = expires_at,
        user_id    = current_user.id,
    ))
    db.commit()
    return {"otp": otp_code, "expires_at": expires_at.isoformat()}


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard endpoint — verify OTP (user pastes OTP from dashboard flow)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/verify-otp", response_model=schemas.OTPVerifyResponse)
def verify_otp(
    payload: schemas.OTPVerifyRequest,
    current_user: models.User = Depends(security.get_current_user),
    db: Session = Depends(database.get_db),
):
    otp_record = (
        db.query(models.TelegramOTP)
        .filter(
            models.TelegramOTP.otp_code == payload.otp_code,
            models.TelegramOTP.used == False,
        )
        .first()
    )

    if not otp_record:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")

    expires = otp_record.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > expires:
        raise HTTPException(status_code=400, detail="OTP has expired")

    if not otp_record.chat_id:
        raise HTTPException(
            status_code=400,
            detail="OTP not yet activated — send it to the Telegram bot first"
        )

    otp_record.used = True

    existing = (
        db.query(models.TelegramLink)
        .filter(models.TelegramLink.user_id == current_user.id)
        .first()
    )
    if existing:
        existing.chat_id = otp_record.chat_id
        existing.enabled = True
    else:
        db.add(models.TelegramLink(
            user_id = current_user.id,
            chat_id = otp_record.chat_id,
            enabled = True,
        ))

    db.commit()
    return {"success": True, "chat_id": otp_record.chat_id}


# ─────────────────────────────────────────────────────────────────────────────
# Telegram webhook — idempotent, device-aware commands
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    db: Session = Depends(database.get_db),
):
    data = await request.json()
    update_id = data.get("update_id")
    if not update_id:
        return {"status": "ignored"}

    # ── Idempotency guard ─────────────────────────────────────────────────
    exists = (
        db.query(models.TelegramUpdate)
        .filter(models.TelegramUpdate.update_id == update_id)
        .first()
    )
    if exists:
        return {"status": "already_processed"}

    db.add(models.TelegramUpdate(update_id=update_id))

    # ── Parse message ─────────────────────────────────────────────────────
    message = data.get("message")
    if not message:
        db.commit()
        return {"status": "ok"}

    chat_id = str(message["chat"]["id"])
    text    = message.get("text", "").strip()

    # ------------------------------------------------------------------
    # /start  → generate an OTP for the user to link in the dashboard
    # ------------------------------------------------------------------
    if text.startswith("/start"):
        otp_code  = _otp()
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)

        db.add(models.TelegramOTP(
            otp_code   = otp_code,
            chat_id    = chat_id,
            expires_at = expires_at,
            user_id    = None,          # user_id filled when dashboard verifies
        ))

        await _send(
            chat_id,
            f"👋 <b>Welcome to SecureCam!</b>\n\n"
            f"Your link code is:\n\n"
            f"<code>{otp_code}</code>\n\n"
            f"Go to your dashboard → Telegram → enter this code.\n"
            f"Expires in 5 minutes.",
        )

    # ------------------------------------------------------------------
    # /devices  → list the user's devices
    # ------------------------------------------------------------------
    elif text.startswith("/devices"):
        link = _get_link(db, chat_id)
        if not link:
            await _send(chat_id, "❌ Account not linked. Send /start and enter the code on the dashboard.")
        else:
            devices = db.query(models.Device).filter(models.Device.user_id == link.user_id).all()
            if not devices:
                await _send(chat_id, "No devices found.")
            else:
                lines = ["<b>Your Devices:</b>"]
                for i, d in enumerate(devices, 1):
                    status = "🔒 Armed" if d.armed else "🔓 Disarmed"
                    lines.append(f"{i}. {d.name or f'Device #{d.id}'} — {status}")
                lines.append("\nUse /arm or /disarm (+ number if multiple devices).")
                await _send(chat_id, "\n".join(lines))

    # ------------------------------------------------------------------
    # /arm [n]  /disarm [n]
    # ------------------------------------------------------------------
    elif text.startswith("/arm") or text.startswith("/disarm"):
        action_arm = text.startswith("/arm")
        parts      = text.split()
        link       = _get_link(db, chat_id)

        if not link:
            await _send(chat_id, "❌ Account not linked. Send /start and enter the code on the dashboard.")
        else:
            devices = db.query(models.Device).filter(models.Device.user_id == link.user_id).all()
            if not devices:
                await _send(chat_id, "No devices found.")
            else:
                target = _resolve_device(devices, parts)

                if target is None:
                    # Multiple devices, no valid index given — show list
                    lines = ["Multiple devices found. Specify a number:\n"]
                    for i, d in enumerate(devices, 1):
                        lines.append(f"{i}. {d.name or f'Device #{d.id}'}")
                    cmd = "/arm" if action_arm else "/disarm"
                    lines.append(f"\nExample: {cmd} 1")
                    await _send(chat_id, "\n".join(lines))
                else:
                    # Control mode check
                    if target.control_mode == models.ControlMode.DASHBOARD_ONLY.value:
                        await _send(
                            chat_id,
                            f"⛔ Device <b>{target.name or target.id}</b> is set to Dashboard-only control."
                        )
                    else:
                        target.armed = action_arm
                        state = "🔒 ARMED" if action_arm else "🔓 DISARMED"
                        await _send(
                            chat_id,
                            f"✅ Device <b>{target.name or f'#{target.id}'}</b> is now {state}."
                        )
                        # Push via WebSocket to the agent (non-blocking)
                        asyncio.create_task(_push_arm_state(target, action_arm))

    db.commit()
    return {"status": "ok"}


# ─────────────────────────────────────────────────────────────────────────────
# Private helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_link(db: Session, chat_id: str) -> models.TelegramLink | None:
    return (
        db.query(models.TelegramLink)
        .filter(
            models.TelegramLink.chat_id == chat_id,
            models.TelegramLink.enabled == True,
        )
        .first()
    )


def _resolve_device(
    devices: list[models.Device], parts: list[str]
) -> models.Device | None:
    """Return the target device, or None if ambiguous."""
    if len(devices) == 1:
        return devices[0]
    # Try to find by 1-based index
    if len(parts) > 1 and parts[1].isdigit():
        idx = int(parts[1]) - 1
        if 0 <= idx < len(devices):
            return devices[idx]
    return None
