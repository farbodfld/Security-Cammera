"""
config_manager.py — Persists device credentials on disk.

Credentials are stored in ~/.securacam/credentials.json (new, packaged-app-safe location).
On first run after an upgrade the manager automatically migrates from the legacy
source-tree location (agent/device_credentials.json) to the new path.
"""

import json
import os
from pathlib import Path

# ── Storage paths ────────────────────────────────────────────────────────────
# New location: writable by packaged binaries on all platforms
_NEW_PATH    = Path.home() / ".securacam" / "credentials.json"

# Legacy location: used by pre-GUI / dev-install versions
_LEGACY_PATH = Path(os.path.dirname(__file__)).parent / "device_credentials.json"

# Default server — overridden by env var at build time
_DEFAULT_SERVER = os.environ.get("SECURACAM_SERVER", "http://127.0.0.1:8000")


class ConfigManager:
    """Read and write the locally stored device credentials."""

    # ── Primary API ───────────────────────────────────────────────────────────

    def get_credentials(self) -> tuple[str | None, str]:
        """
        Returns (device_token, server_url).
        Automatically migrates from the legacy path when found.
        """
        # 1 — new location (preferred)
        if _NEW_PATH.exists():
            return self._read(_NEW_PATH)

        # 2 — legacy location (pre-GUI versions / dev installs)
        if _LEGACY_PATH.exists():
            token, url = self._read(_LEGACY_PATH)
            if token:
                print("[INFO] Migrating credentials to new location…")
                self.save_credentials(token, url)
                try:
                    _LEGACY_PATH.unlink()
                except OSError:
                    pass  # non-fatal
            return token, url

        return None, _DEFAULT_SERVER

    def save_credentials(self, token: str, server_url: str) -> None:
        """Persist both token and server_url to the new credentials path."""
        _NEW_PATH.parent.mkdir(parents=True, exist_ok=True)
        _NEW_PATH.write_text(
            json.dumps({"device_token": token, "server_url": server_url}, indent=2),
            encoding="utf-8",
        )
        print(f"[INFO] Credentials saved → {_NEW_PATH}")

    def clear(self) -> None:
        """Delete saved credentials (used by tray Re-pair action)."""
        for path in (_NEW_PATH, _LEGACY_PATH):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _read(self, path: Path) -> tuple[str | None, str]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data.get("device_token"), data.get("server_url", _DEFAULT_SERVER)
        except Exception:
            return None, _DEFAULT_SERVER

    # ── Backwards-compat shims (used by CLI --pair-code path) ─────────────────

    def get_token(self) -> str | None:
        token, _ = self.get_credentials()
        return token

    def save_token(self, token: str) -> None:
        _, url = self.get_credentials()
        self.save_credentials(token, url)
