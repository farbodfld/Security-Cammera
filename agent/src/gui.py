"""
gui.py — First-run pairing screen for SecuraCam.

Normal user flow:
  - Shows Pair Code + optional Device Name
  - Server URL is hidden behind "Advanced Settings" toggle
  - Default server URL baked-in via SECURACAM_SERVER env var

Blocks until pairing succeeds (self.token is set) or window is closed.
"""

import os
import threading
import customtkinter as ctk
import requests

from config_manager import ConfigManager
from api_client import APIClient

# Default server — set via env var at build time or admin config
_DEFAULT_SERVER = os.environ.get("SECURACAM_SERVER", "http://127.0.0.1:8000")


class PairingWindow:
    """
    First-run setup screen.

    Usage:
        win = PairingWindow()
        token = win.run()   # blocks; returns token str or None
    """

    def __init__(self, default_server: str = _DEFAULT_SERVER):
        self.token: str | None = None
        self._server = default_server
        self._advanced_visible = False

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.root = ctk.CTk()
        self.root.title("SecuraCam — Setup")
        self.root.geometry("440x420")
        self.root.resizable(False, False)
        self._build_ui()

    # ──────────────────────────────────────────────────────────────────────────
    # UI construction
    # ──────────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        r = self.root

        # Header
        ctk.CTkLabel(r, text="🔒 SecuraCam",
                     font=("Inter", 28, "bold")).pack(pady=(36, 4))
        ctk.CTkLabel(r, text="Connect this device to your account",
                     font=("Inter", 13), text_color="gray").pack(pady=(0, 28))

        # Pair Code ── primary field
        ctk.CTkLabel(r, text="Pairing Code", anchor="w",
                     font=("Inter", 12)).pack(fill="x", padx=44)
        self._code_entry = ctk.CTkEntry(
            r, width=352,
            placeholder_text="SC-XXXXXX",
            font=("Courier", 16),
        )
        self._code_entry.pack(padx=44, pady=(4, 14))
        # Allow pressing Enter to trigger pairing
        self._code_entry.bind("<Return>", lambda _e: self._on_pair())

        # Device Name ── optional
        ctk.CTkLabel(r, text="Device Name  (optional)", anchor="w",
                     font=("Inter", 12)).pack(fill="x", padx=44)
        self._name_entry = ctk.CTkEntry(
            r, width=352, placeholder_text="e.g. Living Room Camera")
        self._name_entry.pack(padx=44, pady=(4, 6))

        # Advanced Settings toggle (hidden server URL)
        ctk.CTkButton(
            r, text="⚙  Advanced Settings",
            width=160, height=24,
            fg_color="transparent", hover=False,
            text_color=("gray50", "gray60"),
            font=("Inter", 11),
            command=self._toggle_advanced,
        ).pack(pady=(2, 0))

        # Advanced frame (hidden by default)
        self._adv_frame = ctk.CTkFrame(r, fg_color="transparent")
        self._url_label = ctk.CTkLabel(
            self._adv_frame, text="Server URL", anchor="w",
            font=("Inter", 12))
        self._url_entry = ctk.CTkEntry(
            self._adv_frame, width=352,
            placeholder_text="http://your-backend:8000")
        self._url_entry.insert(0, self._server)

        # Status label
        self._status_lbl = ctk.CTkLabel(
            r, text="", font=("Inter", 12), wraplength=360)
        self._status_lbl.pack(pady=(10, 0))

        # Pair button
        self._btn = ctk.CTkButton(
            r, text="Pair Device",
            width=200, height=40,
            font=("Inter", 14, "bold"),
            command=self._on_pair,
        )
        self._btn.pack(pady=16)

    # ──────────────────────────────────────────────────────────────────────────
    # Event handlers
    # ──────────────────────────────────────────────────────────────────────────

    def _toggle_advanced(self) -> None:
        if self._advanced_visible:
            self._adv_frame.pack_forget()
            self._advanced_visible = False
        else:
            self._adv_frame.pack(padx=44, fill="x", pady=(4, 0))
            self._url_label.pack(anchor="w")
            self._url_entry.pack(pady=(2, 0))
            self._advanced_visible = True

    def _on_pair(self) -> None:
        code = self._code_entry.get().strip().upper()
        url  = (self._url_entry.get().strip().rstrip("/")
                if self._advanced_visible else self._server)
        name = self._name_entry.get().strip() or "My Camera"

        if not code:
            self._set_status("⚠  Please enter the pairing code from your dashboard.", "#f59e0b")
            return

        self._btn.configure(state="disabled", text="Pairing…")
        self._set_status("Contacting server…", "#94a3b8")

        def _worker():
            # ── Step 1: reachability check ────────────────────────────────────
            try:
                requests.get(url, timeout=5)
            except (requests.ConnectionError, requests.Timeout):
                self.root.after(0, lambda: self._on_result(False, None, "network"))
                return
            except Exception:
                self.root.after(0, lambda: self._on_result(False, None, "network"))
                return

            # ── Step 2: pair request ──────────────────────────────────────────
            client = APIClient(url)
            ok, token, detail = client.pair_device(code, device_name=name)
            self.root.after(0, lambda: self._on_result(ok, token, detail))

        threading.Thread(target=_worker, daemon=True, name="pairing").start()

    def _on_result(self, ok: bool, token: str | None, detail: str) -> None:
        if ok and token:
            ConfigManager().save_credentials(token, self._server
                                             if not self._advanced_visible
                                             else self._url_entry.get().strip().rstrip("/"))
            self.token = token
            self._set_status("✓  Paired successfully! Starting camera…", "#4ade80")
            self.root.after(1400, self.root.destroy)
            return

        # ── Granular error messages ───────────────────────────────────────────
        error_map = {
            "PAIR_CODE_INVALID": (
                "✗  Code not recognised. Double-check it and try again.", "#f87171"),
            "PAIR_CODE_EXPIRED": (
                "⏱  That code has expired. Generate a new one in the dashboard.", "#fb923c"),
            "network": (
                "📡  Cannot reach the server. Check your internet connection.", "#f87171"),
        }
        text, color = error_map.get(
            detail, ("✗  Something went wrong. Please try again later.", "#f87171"))
        self._set_status(text, color)
        self._btn.configure(state="normal", text="Pair Device")

    def _set_status(self, message: str, color: str) -> None:
        self._status_lbl.configure(text=message, text_color=color)

    # ──────────────────────────────────────────────────────────────────────────
    # Public
    # ──────────────────────────────────────────────────────────────────────────

    def run(self) -> str | None:
        """Show the window and block until pairing completes or user closes it."""
        self.root.mainloop()
        return self.token
