"""
main.py — Entry point for the Security Camera Agent.

Run with:
    python src/main.py --server-url http://<host>:8000 --pair-code <code>
    python src/main.py                                  # after pairing

Options:
    --pair-code    Pair this agent with the backend (first-time setup)
    --server-url   Backend URL (default: http://127.0.0.1:8000)
    --headless     Run without the OpenCV preview window (for background service)
"""

import sys
import os
import argparse
import traceback

# ── ensure src/ is importable regardless of cwd ──────────────────────────────
_src_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _src_dir)

import cv2
import time
import logging

import config
from detector      import PersonDetector
from event_handler import EventHandler
from display       import FPSCounter, draw_detections, draw_alert_banner, draw_fps, draw_status
from api_client    import APIClient
from config_manager import ConfigManager


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)s  %(name)s  %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )


def open_camera() -> cv2.VideoCapture:
    print(f"[INFO] Opening camera index {config.CAMERA_INDEX} …")
    cap = cv2.VideoCapture(config.CAMERA_INDEX, cv2.CAP_DSHOW)

    if not cap.isOpened():
        print(
            f"[ERROR] Cannot open camera {config.CAMERA_INDEX}.\n"
            "  • Try a different CAMERA_INDEX in src/config.py (0, 1, 2 …).\n"
            "  • Ensure no other app holds the webcam.\n"
            "  • On Windows: Settings → Privacy → Camera."
        )
        sys.exit(1)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  config.FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.FRAME_HEIGHT)
    cap.set(cv2.CAP_PROP_FPS,          config.TARGET_FPS)

    w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    f = cap.get(cv2.CAP_PROP_FPS)
    print(f"[INFO] Camera opened: {w:.0f}×{h:.0f} @ {f:.0f} FPS")
    return cap


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    _setup_logging()

    parser = argparse.ArgumentParser(description="Security Camera Agent")
    parser.add_argument(
        "--pair-code", type=str, default=None,
        help="Pair code (OTP) shown in the dashboard",
    )
    parser.add_argument(
        "--server-url", type=str, default="http://127.0.0.1:8000",
        help="Backend server URL  (default: http://127.0.0.1:8000)",
    )
    parser.add_argument(
        "--headless", action="store_true",
        help="Disable the OpenCV preview window",
    )
    args = parser.parse_args()

    # ── Credentials ──────────────────────────────────────────────────────────
    cfg_mgr    = ConfigManager()
    api_client = APIClient(args.server_url)

    if args.pair_code:
        print(f"[INFO] Pairing with {args.server_url} …")
        ok, token = api_client.pair_device(args.pair_code)
        if not ok or not token:
            print("[ERROR] Pairing failed. Check the code and server URL.")
            sys.exit(1)
        cfg_mgr.save_token(token)
        api_client.set_token(token)
        print("[INFO] Pairing successful! Starting camera …")
    else:
        token = cfg_mgr.get_token()
        if not token:
            print(
                "[ERROR] Agent is not paired.\n"
                "        Run:  python src/main.py --pair-code <CODE> --server-url <URL>"
            )
            sys.exit(1)
        api_client.set_token(token)
        print(f"[INFO] Loaded credentials. Connecting to {args.server_url} …")

    # ── Start WebSocket (daemon thread) ───────────────────────────────────────
    api_client.start_websocket()

    # ── Initialise core components ────────────────────────────────────────────
    detector      = PersonDetector()
    event_handler = EventHandler(api_client=api_client)
    fps_counter   = FPSCounter(window=30)

    # Let armed-state changes from the backend update the event handler live
    api_client.register_callbacks(
        on_armed_change  = lambda armed: setattr(event_handler, "_armed", armed),
        on_config_change = lambda cfg: event_handler.apply_config(cfg),
    )

    cap = open_camera()

    paused      = False
    frame_count = 0
    detections  = []
    alert_active = False
    conf_thresh = config.CONFIDENCE_THRESH

    print("\n[INFO] Security camera running.")
    if args.headless:
        print("       Headless mode — press Ctrl+C to stop.")
    else:
        print("       Q = quit  |  SPACE = pause  |  +/- = confidence  |  Ctrl+C = stop")
    print(f"       Threshold: {conf_thresh:.0%}  |  Cooldown: {config.EVENT_COOLDOWN_SECONDS}s\n")

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("[WARN] Frame read failed — retrying …")
                time.sleep(0.05)
                continue

            frame_count += 1

            # ── Pause handling ────────────────────────────────────────────────
            if paused:
                if not args.headless:
                    cv2.imshow(config.WINDOW_TITLE, frame)
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord("q"):
                        break
                    if key == ord(" "):
                        paused = False
                        print("[INFO] Resumed.")
                else:
                    time.sleep(0.1)
                continue

            # ── Detect ───────────────────────────────────────────────────────
            if frame_count % config.FRAME_SKIP == 0:
                detections = detector.detect(frame)

            # ── Event handling → backend I/O on background thread ─────────────
            alert_active = event_handler.handle(frame, detections)

            # ── Display ───────────────────────────────────────────────────────
            if not args.headless:
                draw_detections(frame, detections)
                if alert_active:
                    draw_alert_banner(frame)
                fps = fps_counter.tick()
                draw_fps(frame, fps)
                draw_status(frame, alert_active)
                cv2.imshow(config.WINDOW_TITLE, frame)

                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    print("[INFO] Q pressed — shutting down …")
                    break
                elif key == ord(" "):
                    paused = True
                    print("[INFO] Paused.")
                elif key in (ord("+"), ord("=")):
                    conf_thresh = min(0.99, conf_thresh + 0.05)
                    config.CONFIDENCE_THRESH = conf_thresh
                    print(f"[INFO] Confidence → {conf_thresh:.0%}")
                elif key == ord("-"):
                    conf_thresh = max(0.05, conf_thresh - 0.05)
                    config.CONFIDENCE_THRESH = conf_thresh
                    print(f"[INFO] Confidence → {conf_thresh:.0%}")

    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user.")
    except Exception:
        traceback.print_exc()
    finally:
        print("[INFO] Releasing resources …")
        api_client.stop_websocket()
        event_handler.shutdown()
        cap.release()
        cv2.destroyAllWindows()
        print("[INFO] Done.")


if __name__ == "__main__":
    main()
