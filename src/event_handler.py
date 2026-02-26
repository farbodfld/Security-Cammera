"""
event_handler.py — Handles person-detection events.

Event trigger logic (presence-state model):
  • An event fires ONLY when the scene transitions from
    'nobody present' → 'person detected'.
  • Once a person has been seen, further detections in the same
    visit do NOT retrigger a snapshot/log/clip.
  • After the frame stays empty for ABSENCE_GRACE_SECONDS the
    presence flag resets, so the next person to walk in counts
    as a new arrival.
  • An optional cooldown (EVENT_COOLDOWN_SECONDS) acts as a
    secondary guard against very-rapid in/out cycling.
"""

import cv2
import os
import sys
import time
import logging
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
import config
import notifier

# ────────────────────────────────────────────────────────────────────────────
# Set up a dedicated file logger (separate from print() statements)
# ────────────────────────────────────────────────────────────────────────────

def _build_logger() -> logging.Logger:
    """Create and return a Logger that writes to logs/detections.log."""
    Path(config.LOGS_DIR).mkdir(parents=True, exist_ok=True)
    log_path = os.path.join(config.LOGS_DIR, config.LOG_FILENAME)

    logger = logging.getLogger("security_cam")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        # File handler — append mode so we keep history across runs
        fh = logging.FileHandler(log_path, encoding="utf-8")
        fh.setLevel(logging.INFO)
        # Console handler — mirror log to terminal
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)

        fmt = logging.Formatter("%(asctime)s  %(levelname)s  %(message)s",
                                datefmt="%Y-%m-%dT%H:%M:%S%z")
        fh.setFormatter(fmt)
        ch.setFormatter(fmt)

        logger.addHandler(fh)
        logger.addHandler(ch)

    return logger


# ────────────────────────────────────────────────────────────────────────────
# ClipWriter — wraps cv2.VideoWriter for timed clip recording
# ────────────────────────────────────────────────────────────────────────────

class ClipWriter:
    """
    Opens a VideoWriter and accepts frames until the target duration is reached.
    Call `is_finished()` each frame; when True the clip is complete and closed.
    """

    def __init__(self, filepath: str, frame_size: tuple[int, int]):
        """
        Parameters
        ----------
        filepath   : full path to output .mp4 file
        frame_size : (width, height) of the frames that will be written
        """
        fourcc = cv2.VideoWriter_fourcc(*config.CLIP_CODEC)
        self._writer   = cv2.VideoWriter(
            filepath, fourcc, config.CLIP_FPS, frame_size
        )
        self._max_frames = int(config.CLIP_DURATION_S * config.CLIP_FPS)
        self._written    = 0
        self._filepath   = filepath

    def write(self, frame) -> None:
        """Write one frame (only while clip is still open)."""
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


# ────────────────────────────────────────────────────────────────────────────
# EventHandler — the main public class
# ────────────────────────────────────────────────────────────────────────────

class EventHandler:
    """
    Call `handle(frame, detections)` every frame.

    Snapshot / log / clip are triggered exactly ONCE per person visit —
    at the moment they first appear in the frame.  They are NOT repeated
    while the same person stays in view.
    """

    # Seconds the frame must stay empty before we consider the person "gone".
    # Prevents a single missed detection (e.g. brief occlusion) from
    # resetting the presence flag and causing a duplicate snapshot.
    ABSENCE_GRACE_SECONDS: float = 2.0

    def __init__(self):
        Path(config.SNAPSHOTS_DIR).mkdir(parents=True, exist_ok=True)
        Path(config.CLIPS_DIR).mkdir(parents=True, exist_ok=True)

        self._logger: logging.Logger = _build_logger()
        self._last_event_time: float = 0.0           # monotonic time of last fired event
        self._active_clip: ClipWriter | None = None   # current clip writer, or None

        # Presence-state tracking
        self._person_present: bool  = False  # True while someone is in the frame
        self._last_seen_time: float = 0.0    # last time a person was detected

        # Notify phone that the camera has started
        notifier.send_session_start()

    # ── public API ────────────────────────────────────────────────────────

    def handle(self, frame, detections: list) -> bool:
        """
        Process this frame's detections.

        Returns True if an alert is currently "active" (a person is present
        OR a clip is still recording), so callers can show the alert banner.
        """
        now   = time.monotonic()
        n_ppl = len(detections)

        # ── Keep active clip fed regardless of anything else ──────────────
        if self._active_clip is not None:
            self._active_clip.write(frame)
            if self._active_clip.is_finished():
                self._logger.info(
                    f"Clip saved → {self._active_clip.filepath}"
                )
                self._active_clip.close()
                self._active_clip = None

        # ── Presence-state machine ────────────────────────────────────────
        if n_ppl > 0:
            # Someone is in the frame right now
            self._last_seen_time = now

            if not self._person_present:
                # ── NEW ARRIVAL: transition from empty → occupied ─────────
                cooldown_ok = (now - self._last_event_time) >= config.EVENT_COOLDOWN_SECONDS
                if cooldown_ok:
                    self._person_present  = True
                    self._last_event_time = now
                    self._fire_event(frame, detections, now)
        else:
            # Frame is currently empty; check the absence grace period
            absent_for = now - self._last_seen_time
            if self._person_present and absent_for >= self.ABSENCE_GRACE_SECONDS:
                # Person has truly left — reset so the next arrival triggers again
                self._person_present = False
                self._logger.info("Person left the frame — monitoring resumed.")

        # ── Active = person visible OR clip still recording ───────────────
        return self._person_present or (self._active_clip is not None)

    def shutdown(self) -> None:
        """Call on exit to flush and close any open clip writer."""
        if self._active_clip is not None:
            self._active_clip.close()
            self._logger.info(
                f"Clip finalised on shutdown → {self._active_clip.filepath}"
            )
            self._active_clip = None
        self._logger.info("Security camera session ended.")
        notifier.send_session_end()

    # ── private helpers ───────────────────────────────────────────────────

    def _fire_event(self, frame, detections: list, timestamp: float) -> None:
        """Called once per debounce window when a person is first detected."""
        iso_ts   = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
        n_people = len(detections)

        # ── Log ─────────────────────────────────────────────────────────
        confs = ", ".join(f"{d.confidence:.0%}" for d in detections)
        self._logger.info(
            f"PERSON DETECTED | count={n_people} | confidences=[{confs}]"
        )

        # ── Snapshot ─────────────────────────────────────────────────────
        if config.SAVE_SNAPSHOTS:
            snap_path = os.path.join(
                config.SNAPSHOTS_DIR, f"snapshot_{iso_ts}.jpg"
            )
            cv2.imwrite(snap_path, frame)
            self._logger.info(f"Snapshot saved → {snap_path}")

        # ── Clip ─────────────────────────────────────────────────────────
        if config.SAVE_CLIPS and self._active_clip is None:
            clip_path = os.path.join(
                config.CLIPS_DIR, f"clip_{iso_ts}.mp4"
            )
            h, w = frame.shape[:2]
            self._active_clip = ClipWriter(clip_path, (w, h))
            self._active_clip.write(frame)   # write the trigger frame first
            self._logger.info(
                f"Recording clip ({config.CLIP_DURATION_S}s) → {clip_path}"
            )

        # ── Telegram alert (non-blocking, runs in background thread) ───────
        # Uses the same frame so the photo on your phone matches the snapshot.
        notifier.send_alert(frame, detections, iso_ts.replace("T", " ").replace("Z", " UTC"))
