"""기한 추출 및 메시지 ID 부여."""

from __future__ import annotations

import hashlib
import re
from datetime import date, datetime, timedelta
from typing import Optional

import pandas as pd
from dateutil import parser as date_parser

_MONTH_DAY = re.compile(
    r"(?:\d{4}[.\-/년\s]*)?(\d{1,2})\s*[월/.\-]\s*(\d{1,2})\s*일?"
)
_ISO_DATE = re.compile(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})")


def message_id(row: pd.Series) -> str:
    raw = "|".join(
        [
            str(row.get("direction", "")),
            str(row.get("counterpart", "")),
            str(row.get("제목", "")),
            str(row.get("날짜/시간", "")),
        ]
    )
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:16]


def extract_deadline(text: str, reference: Optional[date] = None) -> Optional[date]:
    if not text or not str(text).strip():
        return None
    ref = reference or datetime.now().date()
    s = str(text)

    if "오늘" in s:
        return ref
    if "내일" in s:
        return ref + timedelta(days=1)
    if "모레" in s:
        return ref + timedelta(days=2)

    m = _ISO_DATE.search(s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass

    for m in _MONTH_DAY.finditer(s):
        month, day = int(m.group(1)), int(m.group(2))
        try:
            d = date(ref.year, month, day)
            if d < ref - timedelta(days=180):
                d = date(ref.year + 1, month, day)
            return d
        except ValueError:
            continue

    try:
        dt = date_parser.parse(
            s, fuzzy=True, default=datetime(ref.year, ref.month, ref.day)
        )
        return dt.date()
    except (ValueError, TypeError, OverflowError):
        return None


def format_deadline(d: Optional[date]) -> str:
    if d is None:
        return "-"
    return d.strftime("%Y-%m-%d")


def enrich_tasks(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    ids: list[str] = []
    deadlines: list[Optional[date]] = []

    for _, row in out.iterrows():
        ids.append(message_id(row))
        combined = (
            f"{row.get('제목', '')} {row.get('action_summary', '')} {row.get('내용', '')}"
        )
        ref = row.get("parsed_date")
        if ref is not None and pd.notna(ref):
            try:
                ref_date = ref if isinstance(ref, date) else pd.Timestamp(ref).date()
            except Exception:
                ref_date = datetime.now().date()
        else:
            ref_date = datetime.now().date()
        deadlines.append(extract_deadline(combined, ref_date))

    out["message_id"] = ids
    out["deadline"] = deadlines
    out["deadline_display"] = [format_deadline(d) for d in deadlines]
    return out.drop(columns=["urgency", "completed"], errors="ignore")
