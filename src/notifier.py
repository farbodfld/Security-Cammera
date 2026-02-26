"""
notifier.py — Sends Telegram alerts when a person is detected.

Uses the Telegram Bot HTTP API directly via `requests` (already installed
as a transitive dependency of Ultralytics).  Each notification is sent in
a background daemon thread so it never blocks the main detection loop.

Setup (one-time):
  1. Message @BotFather on Telegram → /newbot → copy the BOT_TOKEN.
  2. Message your new bot once (anything), then visit:
       https://api.telegram.org/bot<BOT_TOKEN>/getUpdates
     Copy the "id" value from chat → that is your CHAT_ID.
  3. Paste both values into your .env file (see .env.example).
"""

import os
import io
import threading
import logging
import requests
from pathlib import Path

# Load .env file if python-dotenv is installed (optional but recommended)
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass   # fall back to raw environment variables

logger = logging.getLogger("security_cam")

# Read credentials from environment
_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
_CHAT_ID:   str = os.getenv("TELEGRAM_CHAT_ID",   "")

# Base URL for every Telegram API call
_API_BASE = f"https://api.telegram.org/bot{_BOT_TOKEN}"


def _is_configured() -> bool:
    """Return True if both token and chat ID are set."""
    return bool(_BOT_TOKEN and _CHAT_ID)


# ────────────────────────────────────────────────────────────────────────────
# Internal senders (run inside daemon threads)
# ────────────────────────────────────────────────────────────────────────────

def _send_photo_bytes(jpeg_bytes: bytes, caption: str) -> None:
    """POST a JPEG image + caption to the Telegram sendPhoto endpoint."""
    if not _is_configured():
        return
    try:
        resp = requests.post(
            f"{_API_BASE}/sendPhoto",
            data={"chat_id": _CHAT_ID, "caption": caption, "parse_mode": "Markdown"},
            files={"photo": ("snapshot.jpg", io.BytesIO(jpeg_bytes), "image/jpeg")},
            timeout=10,
        )
        if not resp.ok:
            logger.warning(f"[Telegram] sendPhoto failed: {resp.text}")
    except requests.RequestException as exc:
        logger.warning(f"[Telegram] sendPhoto error: {exc}")


def _send_text(message: str) -> None:
    """POST a plain text message to the Telegram sendMessage endpoint."""
    if not _is_configured():
        return
    try:
        resp = requests.post(
            f"{_API_BASE}/sendMessage",
            data={"chat_id": _CHAT_ID, "text": message, "parse_mode": "Markdown"},
            timeout=10,
        )
        if not resp.ok:
            logger.warning(f"[Telegram] sendMessage failed: {resp.text}")
    except requests.RequestException as exc:
        logger.warning(f"[Telegram] sendMessage error: {exc}")


# ────────────────────────────────────────────────────────────────────────────
# Public API
# ────────────────────────────────────────────────────────────────────────────

def send_alert(frame, detections: list, timestamp_iso: str) -> None:
    """
    Fire a Telegram alert in a background thread.

    Sends the snapshot image with a formatted caption.
    If frame is None, falls back to a text-only message.

    Parameters
    ----------
    frame         : np.ndarray | None  — current OpenCV BGR frame
    detections    : list[Detection]    — person detections for this event
    timestamp_iso : str               — human-readable ISO timestamp string
    """
    if not _is_configured():
        logger.warning(
            "[Telegram] Not configured — set TELEGRAM_BOT_TOKEN and "
            "TELEGRAM_CHAT_ID in your .env file."
        )
        return

    n     = len(detections)
    confs = ", ".join(f"{d.confidence:.0%}" for d in detections)
    caption = (
        f"🚨 *PERSON DETECTED*\n"
        f"🕐 `{timestamp_iso}`\n"
        f"👤 Count: *{n}*\n"
        f"📊 Confidence: `{confs}`"
    )

    if frame is not None:
        import cv2
        # Encode the frame to JPEG in-memory (no temp file needed)
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if ok:
            jpeg_bytes = buf.tobytes()
            t = threading.Thread(
                target=_send_photo_bytes,
                args=(jpeg_bytes, caption),
                daemon=True,   # dies automatically when main program exits
            )
            t.start()
            return

    # Fallback: text-only if frame encoding failed
    t = threading.Thread(target=_send_text, args=(caption,), daemon=True)
    t.start()


def send_session_start() -> None:
    """Notify your phone that the security camera has started."""
    if not _is_configured():
        return
    t = threading.Thread(
        target=_send_text,
        args=("🟢 *Security camera started* — monitoring for persons.",),
        daemon=True,
    )
    t.start()


def send_session_end() -> None:
    """Notify your phone that the security camera has stopped."""
    if not _is_configured():
        return
    t = threading.Thread(
        target=_send_text,
        args=("🔴 *Security camera stopped.*",),
        daemon=True,
    )
    t.start()
