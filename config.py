"""Application constants and path helpers (PyInstaller-safe)."""

from __future__ import annotations

import sys
from pathlib import Path

# --- Categories ---

CATEGORIES: list[dict[str, str]] = [
    {
        "id": "eval",
        "label": "[평가·학력]",
        "folder": "평가·학력",
        "description": "지필/수행평가, 성적 확인, 나이스(NEIS) 입력, 학생부 기재 등",
    },
    {
        "id": "life",
        "label": "[생활·학급]",
        "folder": "생활·학급",
        "description": "출결, 조퇴/외출, 위클래스(상담), 학교폭력 예방, 체육대회 등 학급 경영",
    },
    {
        "id": "admin",
        "label": "[교무·행정]",
        "folder": "교무·행정",
        "description": "전체 교직원 회의, 공문, 연수, 시간표 교체, 복무(초과근무) 등",
    },
    {
        "id": "budget",
        "label": "[예산·물품]",
        "folder": "예산·물품",
        "description": "에듀파인 기안, 교단환경개선비, 비품/기기 대여(노트북, 태블릿) 등",
    },
    {
        "id": "schedule",
        "label": "[주요 일정]",
        "folder": "주요 일정",
        "description": "학사일정, 행사·대회·시험 일정, 개학·방학, 일시·장소 안내 등",
    },
    {
        "id": "etc",
        "label": "[기타]",
        "folder": "기타",
        "description": "친목·인사·감사 등 업무 지시가 없는 사적인 메시지 (최후 선택)",
    },
]

CATEGORY_LABELS: list[str] = [c["label"] for c in CATEGORIES]
LABEL_TO_FOLDER: dict[str, str] = {c["label"]: c["folder"] for c in CATEGORIES}
FOLDER_TO_LABEL: dict[str, str] = {c["folder"]: c["label"] for c in CATEGORIES}

# --- LLM providers ---

LLM_PROVIDERS: dict[str, dict] = {
    "Gemini": {
        "models": [
            "gemini-1.5-pro",
            "gemini-1.5-flash",
            "gemini-2.0-flash",
        ],
        "default_model": "gemini-1.5-pro",
        "key_url": "https://aistudio.google.com/apikey",
    },
    "GPT": {
        "models": [
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
        ],
        "default_model": "gpt-4o-mini",
        "key_url": "https://platform.openai.com/api-keys",
    },
    "Claude": {
        "models": [
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-3-haiku-20240307",
        ],
        "default_model": "claude-3-5-sonnet-20241022",
        "key_url": "https://console.anthropic.com/settings/keys",
    },
}

DEFAULT_PROVIDER = "Gemini"
DEFAULT_GEMINI_MODEL = LLM_PROVIDERS["Gemini"]["default_model"]

ENCODINGS_TO_TRY: tuple[str, ...] = ("utf-8-sig", "utf-8", "cp949", "euc-kr")

RECEIVED_COLUMNS = ("보낸사람", "제목", "날짜/시간", "내용", "첨부파일")
SENT_COLUMNS = ("받은사람", "제목", "날짜/시간", "내용", "첨부파일")


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def get_base_dir() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def get_output_dir() -> Path:
    return get_base_dir() / "output"


def ensure_category_dirs() -> None:
    base = get_output_dir()
    base.mkdir(parents=True, exist_ok=True)
    for cat in CATEGORIES:
        (base / cat["folder"]).mkdir(parents=True, exist_ok=True)
