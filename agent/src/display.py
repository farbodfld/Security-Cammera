"""
display.py — Helper functions for drawing overlays on OpenCV frames.

Kept separate so main.py stays clean and each concern has one home.
"""

import cv2
import time
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
import config


# ────────────────────────────────────────────────────────────────────────────
# FPS counter — uses a rolling average over the last N frames
# ────────────────────────────────────────────────────────────────────────────

class FPSCounter:
    """Smooth FPS estimator using a sliding window of frame timestamps."""

    def __init__(self, window: int = 30):
        self._window   = window          # Number of frames to average over
        self._times: list[float] = []    # Ring buffer of recent frame timestamps

    def tick(self) -> float:
        """Call once per displayed frame. Returns current smoothed FPS."""
        now = time.monotonic()
        self._times.append(now)
        # Keep only the most recent `window` timestamps
        if len(self._times) > self._window:
            self._times.pop(0)
        if len(self._times) < 2:
            return 0.0
        elapsed = self._times[-1] - self._times[0]
        return (len(self._times) - 1) / elapsed if elapsed > 0 else 0.0


# ────────────────────────────────────────────────────────────────────────────
# Drawing functions
# ────────────────────────────────────────────────────────────────────────────

def draw_detections(frame, detections: list) -> None:
    """
    Draw a bounding box + confidence label for every Detection in the list.
    Modifies `frame` in-place.
    """
    for det in detections:
        # Bounding rectangle
        cv2.rectangle(
            frame,
            (det.x1, det.y1),
            (det.x2, det.y2),
            config.BOX_COLOR,
            config.BOX_THICKNESS,
        )
        # Label: "Person 87%"
        label = f"Person {det.confidence:.0%}"
        # Small filled rectangle behind text for readability
        (tw, th), baseline = cv2.getTextSize(
            label, cv2.FONT_HERSHEY_SIMPLEX, config.FONT_SCALE, 2
        )
        cv2.rectangle(
            frame,
            (det.x1, det.y1 - th - baseline - 4),
            (det.x1 + tw, det.y1),
            config.BOX_COLOR,
            -1,  # filled
        )
        cv2.putText(
            frame, label,
            (det.x1, det.y1 - baseline - 2),
            cv2.FONT_HERSHEY_SIMPLEX,
            config.FONT_SCALE,
            (0, 0, 0),   # black text on coloured background
            2,
        )


def draw_alert_banner(frame) -> None:
    """
    Draw a prominent red "⚠ PERSON DETECTED" banner at the top of the frame.
    Modifies `frame` in-place.
    """
    h, w = frame.shape[:2]
    banner_h = 40
    overlay  = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, banner_h), config.ALERT_COLOR, -1)
    # Blend semi-transparently
    cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)
    cv2.putText(
        frame,
        "!! PERSON DETECTED !!",
        (10, 28),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.85,
        (255, 255, 255),
        2,
    )


def draw_fps(frame, fps: float) -> None:
    """Draw the current FPS in the top-right corner."""
    if not config.SHOW_FPS:
        return
    h, w = frame.shape[:2]
    text = f"FPS: {fps:.1f}"
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
    cv2.putText(
        frame, text,
        (w - tw - 10, th + 10),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (255, 255, 0),   # yellow
        2,
    )


def draw_status(frame, active: bool) -> None:
    """Draw a small coloured status dot + text in the bottom-left corner."""
    h, w = frame.shape[:2]
    color  = (0, 0, 255) if active else (0, 200, 0)
    label  = "ALERT" if active else "MONITORING"
    cv2.circle(frame, (18, h - 18), 8, color, -1)
    cv2.putText(
        frame, label,
        (32, h - 12),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        color,
        2,
    )
