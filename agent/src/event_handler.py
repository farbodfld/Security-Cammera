"""
event_handler.py — Handles person-detection events.

Event trigger logic (presence-state model):
  • An event fires ONLY when the scene transitions from
    'nobody present' → 'person detected'.
  • Once a person has been seen, further detections in the same
    visit do NOT re-trigger a snapshot/log/clip.
  • After the frame stays empty for ABSENCE_GRACE_SECONDS the
    presence flag resets, so the next person counts as a new arrival.
  • An optional cooldown (EVENT_COOLDOWN_SECONDS) guards against
    rapid in/out cycling.

Backend integration:
  • On each new event: POST /events, then POST /events/{id}/snapshot
    (runs in a background thread so it never blocks the camera loop).
"""

import cv2
import os
import sys
import time
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
import config

logger = logging.getLogger("event_handler")


# ─────────────────────────────────────────────────────────────────────────────
# File logger (mirrors existing logs/detections.log behaviour)
# ─────────────────────────────────────────────────────────────────────────────

def _build_file_logger() -> logging.Logger:
    Path(config.LOGS_DIR).mkdir(parents=True, exist_ok=True)
    log_path = os.path.join(config.LOGS_DIR, config.LOG_FILENAME)

    ev_logger = logging.getLogger("security_cam")
    ev_logger.setLevel(logging.INFO)

    if not ev_logger.handlers:
        fh = logging.FileHandler(log_path, encoding="utf-8")
        fh.setLevel(logging.INFO)
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        fmt = logging.Formatter(
            "%(asctime)s  %(levelname)s  %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
        fh.setFormatter(fmt)
        ch.setFormatter(fmt)
        ev_logger.addHandler(fh)
        ev_logger.addHandler(ch)

    return ev_logger


# ─────────────────────────────────────────────────────────────────────────────
# ClipWriter
# ─────────────────────────────────────────────────────────────────────────────

class ClipWriter:
    def __init__(self, filepath: str, frame_size: tuple[int, int]):
        fourcc = cv2.VideoWriter_fourcc(*config.CLIP_CODEC)
        self._writer     = cv2.VideoWriter(filepath, fourcc, config.CLIP_FPS, frame_size)
        self._max_frames = int(config.CLIP_DURATION_S * config.CLIP_FPS)
        self._written    = 0
        self._filepath   = filepath

    def write(self, frame) -> None:
        if not self.is_finished():
            self._writer.write(frame)
            self._written += 1

    def is_finished(self) -> bool:
        return self._written >= self._max_frames

    def close(self) -> None:
        self._writer.release()

    @property
    def filepath(self) -> str:
        return self._filepath


# ─────────────────────────────────────────────────────────────────────────────
# EventHandler
# ─────────────────────────────────────────────────────────────────────────────

class EventHandler:
    """
    Call `handle(frame, detections)` once per camera frame.

    Pass an `api_client` (APIClient instance) to enable backend reporting.
    If omitted the handler works fully offline (local log + snapshot).
    """

    ABSENCE_GRACE_SECONDS: float = 2.0

    def __init__(self, api_client=None):
        Path(config.SNAPSHOTS_DIR).mkdir(parents=True, exist_ok=True)
        Path(config.CLIPS_DIR).mkdir(parents=True, exist_ok=True)

        self._file_logger = _build_file_logger()
        self._api          = api_client          # may be None (offline mode)

        self._last_event_time: float       = 0.0
        self._active_clip: ClipWriter | None = None

        # Presence-state
        self._person_present: bool  = False
        self._last_seen_time: float = 0.0

        # Armed state — updated live via WebSocket callback
        self._armed: bool = True

    # ── Public API ────────────────────────────────────────────────────────────

    def handle(self, frame, detections: list) -> bool:
        now   = time.monotonic()
        n_ppl = len(detections)

        # ── Feed active clip regardless of anything else ───────────────────
        if self._active_clip is not None:
            self._active_clip.write(frame)
            if self._active_clip.is_finished():
                self._file_logger.info(f"Clip saved → {self._active_clip.filepath}")
                self._active_clip.close()
                self._active_clip = None

        # ── Presence-state machine ────────────────────────────────────────
        if n_ppl > 0:
            self._last_seen_time = now

            if not self._person_present:
                cooldown_ok = (now - self._last_event_time) >= config.EVENT_COOLDOWN_SECONDS
                if cooldown_ok:
                    self._person_present  = True
                    self._last_event_time = now
                    if self._armed:
                        self._fire_event(frame, detections, now)
                    else:
                        self._file_logger.info("PERSON DETECTED (disarmed — not reporting)")
        else:
            absent_for = now - self._last_seen_time
            if self._person_present and absent_for >= self.ABSENCE_GRACE_SECONDS:
                self._person_present = False
                self._file_logger.info("Person left the frame — monitoring resumed.")

        return self._person_present or (self._active_clip is not None)

    def apply_config(self, cfg: dict) -> None:
        """Apply configuration updates pushed from the backend."""
        if "confidence_threshold" in cfg and cfg["confidence_threshold"] is not None:
            config.CONFIDENCE_THRESH = float(cfg["confidence_threshold"])
            logger.info(f"Config applied: confidence_threshold={config.CONFIDENCE_THRESH}")
        if "snapshot_enabled" in cfg:
            config.SAVE_SNAPSHOTS = bool(cfg["snapshot_enabled"])
            logger.info(f"Config applied: snapshot_enabled={config.SAVE_SNAPSHOTS}")

    def shutdown(self) -> None:
        if self._active_clip is not None:
            self._active_clip.close()
            self._file_logger.info(f"Clip finalised on shutdown → {self._active_clip.filepath}")
            self._active_clip = None
        self._file_logger.info("Security camera session ended.")

    # ── Private helpers ───────────────────────────────────────────────────────

    def _fire_event(self, frame, detections: list, timestamp: float) -> None:
        """Called once per debounce window on first detection."""
        now_utc  = datetime.now(timezone.utc)
        iso_ts   = now_utc.strftime("%Y-%m-%dT%H-%M-%SZ")
        n_people = len(detections)
        confs    = ", ".join(f"{d.confidence:.0%}" for d in detections)
        best_conf = max(d.confidence for d in detections)

        self._file_logger.info(
            f"PERSON DETECTED | count={n_people} | confidences=[{confs}]"
        )

        # ── Local snapshot ────────────────────────────────────────────────
        snap_path: str | None = None
        if config.SAVE_SNAPSHOTS:
            snap_path = os.path.join(config.SNAPSHOTS_DIR, f"snapshot_{iso_ts}.jpg")
            cv2.imwrite(snap_path, frame)
            self._file_logger.info(f"Snapshot saved → {snap_path}")

        # ── Local clip ────────────────────────────────────────────────────
        if config.SAVE_CLIPS and self._active_clip is None:
            clip_path = os.path.join(config.CLIPS_DIR, f"clip_{iso_ts}.mp4")
            h, w = frame.shape[:2]
            self._active_clip = ClipWriter(clip_path, (w, h))
            self._active_clip.write(frame)
            self._file_logger.info(f"Recording clip ({config.CLIP_DURATION_S}s) → {clip_path}")

        # ── Backend report (non-blocking) ─────────────────────────────────
        if self._api is not None:
            threading.Thread(
                target=self._report_to_backend,
                args=(best_conf, now_utc, snap_path),
                daemon=True,
                name="event-report",
            ).start()

    def _report_to_backend(
        self, confidence: float, happened_at: datetime, snap_path: str | None
    ) -> None:
        """Posts the event and optional snapshot to the backend (background thread)."""
        event_id = self._api.post_event(confidence, happened_at)
        if event_id is None:
            logger.warning("Failed to report event to backend.")
            return

        logger.info(f"Event reported → id={event_id}")

        if snap_path and self._api.snapshot_enabled:
            ok = self._api.upload_snapshot(event_id, snap_path)
            if ok:
                logger.info(f"Snapshot uploaded → event_id={event_id}")
            else:
                logger.warning(f"Snapshot upload failed for event_id={event_id}")
