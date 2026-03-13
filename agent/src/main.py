"""
main.py — Entry point for the Security Camera Agent.

First-run (no saved credentials):
    App shows a GUI pairing screen automatically.

After pairing (credentials saved):
    App skips GUI and goes straight to monitoring.

Developer / CLI path (bypasses GUI entirely):
    python src/main.py --pair-code SC-XXXXXX [--server-url URL] [--headless]
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
        help="Pair code (OTP) shown in the dashboard — developer/CLI path",
    )
    parser.add_argument(
        "--server-url", type=str, default=None,
        help="Backend server URL (overrides saved URL; default: reads from credentials)",
    )
    parser.add_argument(
        "--headless", action="store_true",
        help="Disable the OpenCV preview window and system tray (background service mode)",
    )
    args = parser.parse_args()

    cfg_mgr = ConfigManager()

    # ── Resolve server URL ─────────────────────────────────────────────────────────
    saved_token, saved_url = cfg_mgr.get_credentials()
    server_url = args.server_url or saved_url

    # ── CLI path (developer) ─────────────────────────────────────────────────────────
    if args.pair_code:
        print(f"[INFO] CLI pairing with {server_url} …")
        api_client = APIClient(server_url)
        ok, token, detail = api_client.pair_device(args.pair_code)
        if not ok or not token:
            msg = {
                "PAIR_CODE_INVALID": "Pair code not recognised.",
                "PAIR_CODE_EXPIRED": "Pair code has expired.",
                "network":           "Cannot reach the server.",
            }.get(detail, "Pairing failed.")
            print(f"[ERROR] {msg}")
            sys.exit(1)
        cfg_mgr.save_credentials(token, server_url)
        api_client.set_token(token)
        print("[INFO] CLI pairing successful! Starting camera …")

    # ── GUI / normal-user path ───────────────────────────────────────────────────────
    else:
        if not saved_token:
            # First run — show pairing screen
            from gui import PairingWindow
            win = PairingWindow(default_server=server_url)
            token = win.run()
            if not token:
                print("[INFO] Setup cancelled by user.")
                sys.exit(0)
            # Reload credentials that the GUI just saved
            token, server_url = cfg_mgr.get_credentials()
        else:
            token = saved_token

        api_client = APIClient(server_url)
        api_client.set_token(token)
        print(f"[INFO] Loaded credentials. Connecting to {server_url} …")

    # ── System tray ───────────────────────────────────────────────────────────────
    tray_mgr = None
    if not args.headless:
        from tray import start_tray
        tray_mgr = start_tray(on_quit=lambda: os._exit(0))

    # ── Start WebSocket (daemon thread) ─────────────────────────────────────────────────
    api_client.start_websocket()

    # ── Initialise core components ──────────────────────────────────────────────────────
    detector      = PersonDetector()
    event_handler = EventHandler(api_client=api_client)
    fps_counter   = FPSCounter(window=30)

    # Let armed-state changes from the backend update the event handler live
    def _on_armed_change(armed: bool) -> None:
        setattr(event_handler, "_armed", armed)
        if tray_mgr:
            tray_mgr.update_state(armed=armed, connected=True)

    def _on_ws_connected() -> None:
        if tray_mgr:
            tray_mgr.update_state(armed=api_client.armed, connected=True)

    def _on_ws_disconnected() -> None:
        if tray_mgr:
            tray_mgr.update_state(armed=api_client.armed, connected=False)

    api_client.register_callbacks(
        on_armed_change  = _on_armed_change,
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
