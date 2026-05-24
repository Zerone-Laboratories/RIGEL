"""Helpers for optional Rigel voice asset locations."""

from __future__ import annotations

import os
from pathlib import Path


DEFAULT_ASSETS_ROOT = Path.home() / ".cache" / "rigel" / "voice-assets"


def get_assets_root() -> str:
    """Return the root directory expected to contain voice assets."""
    env = os.getenv("RIGEL_VOICE_ASSETS_DIR")
    if env:
        return str(Path(env).expanduser().resolve())
    return str(DEFAULT_ASSETS_ROOT)


def get_synthesis_assets_dir() -> str:
    """Return directory expected to contain Piper .onnx voice files."""
    return str(Path(get_assets_root()) / "synthesis_assets")


def get_whisper_live_dir() -> str:
    """Return directory expected to contain whisper-live binaries/models/libs."""
    return str(Path(get_assets_root()) / "whisper_live")


def setup_guide() -> str:
    root = get_assets_root()
    return (
        "Rigel voice assets package is installed, but binary/model files are not bundled by default.\n"
        "Expected asset root: "
        f"{root}\n"
        "Setup guide:\n"
        "1. Download or copy Rigel voice assets into the expected root\n"
        "2. Ensure these paths exist:\n"
        f"   - {Path(root) / 'synthesis_assets'}\n"
        f"   - {Path(root) / 'whisper_live'}\n"
        "3. Or set RIGEL_SYNTHESIS_ASSETS_DIR and RIGEL_WHISPER_LIVE_DIR explicitly"
    )
