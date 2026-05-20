"""Shared data types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class MessageRecord:
    """Normalized messenger row."""

    direction: str  # "받음" | "보냄"
    counterpart: str
    title: str
    datetime_raw: str
    content: str
    attachments_raw: str
    parsed_date: Optional[date] = None
    source_file: str = ""

    @property
    def has_attachment(self) -> bool:
        return bool(self.attachments_raw and str(self.attachments_raw).strip())


@dataclass
class ClassificationResult:
    category_label: str
    action_summary: str
    error: Optional[str] = None


@dataclass
class AttachmentRouteResult:
    filename: str
    source_path: Optional[str] = None
    dest_path: Optional[str] = None
    status: str = "대기"  # 성공 | 실패 | 미발견 | 대기
    message: str = ""


@dataclass
class ProcessedMessage:
    record: MessageRecord
    classification: ClassificationResult = field(
        default_factory=lambda: ClassificationResult("[기타]", "", None)
    )
    attachment_results: list[AttachmentRouteResult] = field(default_factory=list)
