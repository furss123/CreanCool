"""로컬 사용자 설정 저장 (API 키·경로 기억하기)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import config

PREFS_FILE = config.get_base_dir() / ".user_prefs.json"


def load_prefs() -> dict[str, Any]:
    if not PREFS_FILE.exists():
        return {"remember": False}
    try:
        data = json.loads(PREFS_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return {"remember": False}


def save_prefs(
    remember: bool,
    api_key: str = "",
    model: str = "",
    attach_dir: str = "",
) -> None:
    if remember:
        payload = {
            "remember": True,
            "gemini_api_key": api_key,
            "gemini_model": model,
            "attach_dir": attach_dir,
        }
    else:
        payload = {"remember": False}
    try:
        PREFS_FILE.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass


def get_field(key: str, fallback: str = "") -> str:
    prefs = load_prefs()
    if not prefs.get("remember"):
        return fallback
    val = prefs.get(key, fallback)
    return str(val) if val is not None else fallback
