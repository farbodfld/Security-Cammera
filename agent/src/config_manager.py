"""
config_manager.py — Persists device credentials on disk.

The device token is stored in a tiny JSON file next to the agent
so the agent knows it's paired after first run.
"""

import json
import os
from pathlib import Path

# Store credentials one level above src/ so it survives code changes
_CREDS_PATH = Path(os.path.dirname(__file__)).parent / "device_credentials.json"


class ConfigManager:
    """Read and write the locally stored device token."""

    def get_token(self) -> str | None:
        """Return the saved device_token, or None if not paired yet."""
        if not _CREDS_PATH.exists():
            return None
        try:
            data = json.loads(_CREDS_PATH.read_text(encoding="utf-8"))
            return data.get("device_token")
        except Exception:
            return None

    def save_token(self, token: str) -> None:
        """Persist the device_token to disk."""
        _CREDS_PATH.write_text(
            json.dumps({"device_token": token}, indent=2),
            encoding="utf-8",
        )
        print(f"[INFO] Credentials saved → {_CREDS_PATH}")

    def clear(self) -> None:
        """Delete saved credentials (unpair the device)."""
        if _CREDS_PATH.exists():
            _CREDS_PATH.unlink()
