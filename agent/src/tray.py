"""
tray.py — System tray icon for SecuraCam monitoring mode.

Provides:
  - Live status (connected / armed state)
  - "Open Dashboard" — opens browser to the web dashboard
  - "Re-pair / Reset Device" — clears credentials and quits (next launch shows setup)
  - "Quit SecuraCam"

Platform notes:
  - Windows:    Full support via pystray + Pillow
  - macOS:      Full support; icon appears in menu bar (app needs to be signed for Gatekeeper)
  - Linux:      Requires libappindicator3 or libayatana-appindicator.
                GNOME 40+ hides tray icons by default — advise users to install the
                "AppIndicator and KStatusNotifierItem Support" GNOME Shell extension.
"""

import os
import threading
import webbrowser
import logging

import pystray
from PIL import Image, ImageDraw

logger = logging.getLogger("tray")

# Dashboard URL — configure via env var at build time
DASHBOARD_URL = os.environ.get("SECURACAM_DASHBOARD_URL", "http://127.0.0.1:3000")


# ─────────────────────────────────────────────────────────────────────────────
# Icon rendering
# ─────────────────────────────────────────────────────────────────────────────

def _render_icon(armed: bool = True) -> Image.Image:
    """Draw a 64×64 RGBA icon. Indigo = armed/active, slate = disarmed."""
    fill_color = (99, 102, 241) if armed else (71, 85, 105)
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d   = ImageDraw.Draw(img)
    d.ellipse([4, 4, 60, 60], fill=fill_color)
    # Lock body
    d.rectangle([22, 30, 42, 50], fill="white", outline="white")
    # Lock shackle
    d.arc([26, 14, 38, 34], start=0, end=180, fill="white", width=4)
    return img


# ─────────────────────────────────────────────────────────────────────────────
# Tray manager
# ─────────────────────────────────────────────────────────────────────────────

class TrayManager:
    """
    Manages the system tray icon lifecycle.

    Call start() to launch in a daemon thread.
    Call update_state(armed, connected) from any thread to refresh the icon and menu.
    """

    def __init__(self, on_quit):
        self._on_quit    = on_quit
        self._armed      = True
        self._connected  = False
        self._icon: pystray.Icon | None = None

    # ── State ─────────────────────────────────────────────────────────────────

    def update_state(self, armed: bool, connected: bool) -> None:
        """Thread-safe status update — refreshes icon image and menu label."""
        self._armed     = armed
        self._connected = connected
        if self._icon:
            try:
                self._icon.icon = _render_icon(armed)
                self._icon.update_menu()
            except Exception as exc:
                logger.debug("Tray update_menu failed: %s", exc)

    # ── Menu construction ─────────────────────────────────────────────────────

    def _status_text(self) -> str:
        conn  = "🟢 Connected"    if self._connected else "🔴 Disconnected"
        state = "🔒 Monitoring"   if self._armed     else "⏸  Disarmed"
        return f"{conn}  ·  {state}"

    def _build_menu(self) -> pystray.Menu:
        return pystray.Menu(
            pystray.MenuItem(self._status_text(), None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Open Dashboard",
                             lambda icon, item: webbrowser.open(DASHBOARD_URL)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Re-pair / Reset Device", self._handle_repair),
            pystray.MenuItem("Quit SecuraCam",         self._handle_quit),
        )

    # ── Handlers ──────────────────────────────────────────────────────────────

    def _handle_repair(self, icon, item) -> None:
        """Clear credentials so next launch shows the pairing screen, then quit."""
        logger.info("Re-pair requested from tray — clearing credentials.")
        try:
            from config_manager import ConfigManager
            ConfigManager().clear()
        except Exception as exc:
            logger.warning("Could not clear credentials: %s", exc)
        self._handle_quit(icon, item)

    def _handle_quit(self, icon, item) -> None:
        logger.info("Quit requested from tray.")
        icon.stop()
        self._on_quit()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def run(self) -> None:
        """Block until the tray icon is stopped. Call from a dedicated thread."""
        self._icon = pystray.Icon(
            "SecuraCam",
            _render_icon(self._armed),
            "SecuraCam",
            self._build_menu(),
        )
        self._icon.run()


# ─────────────────────────────────────────────────────────────────────────────
# Public factory
# ─────────────────────────────────────────────────────────────────────────────

def start_tray(on_quit) -> TrayManager:
    """
    Launch the tray icon in a daemon thread.

    Returns the TrayManager so the caller can call update_state() later.

    Example:
        tray = start_tray(on_quit=lambda: os._exit(0))
        # later, when WebSocket state changes:
        tray.update_state(armed=True, connected=True)
    """
    mgr = TrayManager(on_quit=on_quit)
    t   = threading.Thread(target=mgr.run, daemon=True, name="tray")
    t.start()
    return mgr
