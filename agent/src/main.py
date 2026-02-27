"""
main.py — Entry point for the Security Camera application.

Run with:
    python src/main.py

Controls:
    Q          — quit
    S          — force-save a manual snapshot right now
    SPACE      — pause / resume
    +  /  -    — increase / decrease confidence threshold in real-time

Architecture summary
─────────────────────────────────────────────────────────
  ┌─────────────┐     frames     ┌──────────────┐
  │ cv2.VideoCapture │──────────▶│ PersonDetector│
  └─────────────┘                └──────┬───────┘
                                        │ detections
                          ┌─────────────▼────────────┐
                          │       EventHandler        │
                          │  debounce / log /         │
                          │  snapshot / clip writer   │
                          └─────────────┬─────────────┘
                                        │ alert_active flag
                          ┌─────────────▼─────────────┐
                          │  display helpers           │
                          │  draw_detections / banner  │
                          │  draw_fps / draw_status    │
                          └─────────────┬──────────────┘
                                        │
                          ┌─────────────▼──────────────┐
                          │   cv2.imshow (preview win) │
                          └────────────────────────────┘
"""

import sys
import os

# Ensure the src/ directory is on the Python path so relative imports work
# whether this file is run as `python src/main.py` or `python main.py`.
_src_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _src_dir)

import cv2
import time
import logging

import config
from detector      import PersonDetector
from event_handler import EventHandler
from display       import FPSCounter, draw_detections, draw_alert_banner, draw_fps, draw_status


# ────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────

def open_camera() -> cv2.VideoCapture:
    """
    Opens the webcam and sets desired resolution + FPS.
    Exits the program gracefully if the camera cannot be opened.
    """
    print(f"[INFO] Opening camera index {config.CAMERA_INDEX} …")
    cap = cv2.VideoCapture(config.CAMERA_INDEX, cv2.CAP_DSHOW)  # CAP_DSHOW = faster on Windows

    if not cap.isOpened():
        print(
            f"[ERROR] Cannot open camera {config.CAMERA_INDEX}.\n"
            "  • Try changing CAMERA_INDEX in src/config.py (0, 1, 2 …).\n"
            "  • Ensure no other application is using the webcam.\n"
            "  • On Windows, check Privacy > Camera in Settings."
        )
        sys.exit(1)

    # Request resolution/FPS — the driver may clamp to its own limits
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  config.FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.FRAME_HEIGHT)
    cap.set(cv2.CAP_PROP_FPS,          config.TARGET_FPS)

    actual_w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    actual_h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    actual_f = cap.get(cv2.CAP_PROP_FPS)
    print(f"[INFO] Camera opened: {actual_w:.0f}×{actual_h:.0f} @ {actual_f:.0f} FPS")
    return cap


def save_manual_snapshot(frame, logger: logging.Logger) -> None:
    """Save a snapshot right now, triggered by the user pressing S."""
    from datetime import datetime, timezone
    from pathlib import Path
    import os as _os
    Path(config.SNAPSHOTS_DIR).mkdir(parents=True, exist_ok=True)
    ts   = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    path = _os.path.join(config.SNAPSHOTS_DIR, f"manual_{ts}.jpg")
    cv2.imwrite(path, frame)
    logger.info(f"Manual snapshot saved → {path}")


# ────────────────────────────────────────────────────────────────────────────
# Main capture loop
# ────────────────────────────────────────────────────────────────────────────

def main() -> None:
    # ── Initialise components ────────────────────────────────────────────
    detector      = PersonDetector()
    event_handler = EventHandler()
    fps_counter   = FPSCounter(window=30)
    logger        = logging.getLogger("security_cam")

    cap = open_camera()

    paused       = False
    frame_count  = 0           # Total frames read (used for FRAME_SKIP logic)
    detections   = []          # Latest detection results (reused across skipped frames)
    alert_active = False       # True while person present / clip recording
    conf_thresh  = config.CONFIDENCE_THRESH   # Live-adjustable

    print("\n[INFO] Security camera running.")
    print("       Q = quit  |  S = manual snapshot  |  SPACE = pause  |  +/- = confidence")
    print(f"       Confidence threshold: {conf_thresh:.0%}")
    print(f"       Cooldown: {config.EVENT_COOLDOWN_SECONDS}s  |  Clip duration: {config.CLIP_DURATION_S}s\n")

    try:
        while True:
            # ── Read frame ───────────────────────────────────────────────
            ret, frame = cap.read()
            if not ret:
                print("[WARN] Failed to read frame — retrying …")
                time.sleep(0.05)
                continue

            frame_count += 1

            if paused:
                # Still show the last frame so the window stays responsive
                cv2.imshow(config.WINDOW_TITLE, frame)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break
                if key == ord(" "):
                    paused = False
                    print("[INFO] Resumed.")
                continue

            # ── Detection (with optional frame skipping) ──────────────────
            # FRAME_SKIP=1 → detect every frame (default)
            # FRAME_SKIP=2 → detect every 2nd frame, show previous boxes on skipped frames
            if frame_count % config.FRAME_SKIP == 0:
                detections = detector.detect(frame)

            # ── Event handling ────────────────────────────────────────────
            # The event handler decides whether to log/snapshot/clip,
            # and tells us whether an alert banner should be shown.
            alert_active = event_handler.handle(frame, detections)

            # ── Draw overlays ─────────────────────────────────────────────
            draw_detections(frame, detections)
            if alert_active:
                draw_alert_banner(frame)
            fps = fps_counter.tick()
            draw_fps(frame, fps)
            draw_status(frame, alert_active)

            # ── Show window ───────────────────────────────────────────────
            cv2.imshow(config.WINDOW_TITLE, frame)

            # ── Keyboard control ──────────────────────────────────────────
            # waitKey(1) = block 1 ms so OpenCV can refresh the window;
            # & 0xFF masks to the lower byte for cross-platform safety.
            key = cv2.waitKey(1) & 0xFF

            if key == ord("q"):
                print("[INFO] Q pressed — shutting down …")
                break

            elif key == ord("s"):
                save_manual_snapshot(frame, logger)

            elif key == ord(" "):
                paused = True
                print("[INFO] Paused. Press SPACE again to resume.")

            elif key == ord("+") or key == ord("="):
                conf_thresh = min(0.99, conf_thresh + 0.05)
                config.CONFIDENCE_THRESH = conf_thresh
                print(f"[INFO] Confidence threshold raised to {conf_thresh:.0%}")

            elif key == ord("-"):
                conf_thresh = max(0.05, conf_thresh - 0.05)
                config.CONFIDENCE_THRESH = conf_thresh
                print(f"[INFO] Confidence threshold lowered to {conf_thresh:.0%}")

    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user (Ctrl+C).")

    finally:
        # ── Graceful shutdown ─────────────────────────────────────────────
        print("[INFO] Releasing resources …")
        event_handler.shutdown()
        cap.release()
        cv2.destroyAllWindows()
        print("[INFO] Done. Goodbye!")


# ────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    main()
