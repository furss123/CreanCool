"""로컬 사용자 설정 저장."""

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
    llm_provider: str = "",
    llm_model: str = "",
    attach_dir: str = "",
) -> None:
    if remember:
        payload = {
            "remember": True,
            "api_key": api_key,
            "llm_provider": llm_provider,
            "llm_model": llm_model,
            "attach_dir": attach_dir,
            # 하위 호환
            "gemini_api_key": api_key,
            "gemini_model": llm_model,
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
    if not val and key == "api_key":
        val = prefs.get("gemini_api_key", fallback)
    if not val and key == "llm_model":
        val = prefs.get("gemini_model", fallback)
    return str(val) if val is not None else fallback
