"""Attachment discovery and copy into category folders."""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Optional

import config
from src.models import AttachmentRouteResult, ProcessedMessage

ATTACHMENT_SEPARATORS = re.compile(r"[;；\n]+|,(?=\S)")


def split_attachment_names(raw: str) -> list[str]:
    if not raw or not str(raw).strip():
        return []
    text = str(raw).strip()
    parts = ATTACHMENT_SEPARATORS.split(text)
    names: list[str] = []
    for p in parts:
        name = p.strip().strip('"').strip("'")
        if name and name.lower() not in ("nan", "none", "-"):
            names.append(name)
    return names


def find_file_in_folder(filename: str, search_root: Path) -> Optional[Path]:
    if not search_root.is_dir():
        return None
    direct = search_root / filename
    if direct.is_file():
        return direct
    target_lower = filename.lower()
    for path in search_root.rglob("*"):
        if path.is_file() and path.name.lower() == target_lower:
            return path
    return None


def route_attachments_for_message(
    msg: ProcessedMessage,
    download_dir: Path,
    dry_run: bool = False,
) -> list[AttachmentRouteResult]:
    config.ensure_category_dirs()
    folder_name = config.LABEL_TO_FOLDER.get(
        msg.classification.category_label, "기타"
    )
    dest_dir = config.get_output_dir() / folder_name
    dest_dir.mkdir(parents=True, exist_ok=True)

    results: list[AttachmentRouteResult] = []
    for name in split_attachment_names(msg.record.attachments_raw):
        result = AttachmentRouteResult(filename=name)
        source = find_file_in_folder(name, download_dir)
        if source is None:
            result.status = "미발견"
            result.message = f"'{download_dir}' 에서 파일을 찾지 못함"
            results.append(result)
            continue
        result.source_path = str(source)
        dest = dest_dir / source.name
        if dry_run:
            result.dest_path = str(dest)
            result.status = "대기"
            result.message = "복사 대기"
            results.append(result)
            continue
        try:
            shutil.copy2(source, dest)
            result.dest_path = str(dest)
            result.status = "성공"
            result.message = "복사 완료"
        except OSError as e:
            result.status = "실패"
            result.message = str(e)
        results.append(result)
    return results


def route_all_attachments(
    messages: list[ProcessedMessage],
    download_dir: str,
    only_with_attachments: bool = True,
) -> tuple[int, int]:
    """
    Returns (success_count, attempt_count).
    """
    root = Path(download_dir)
    if not root.is_dir():
        raise FileNotFoundError(f"첨부파일 폴더가 존재하지 않습니다: {download_dir}")

    success = 0
    attempts = 0
    for msg in messages:
        if only_with_attachments and not msg.record.has_attachment:
            continue
        results = route_attachments_for_message(msg, root, dry_run=False)
        msg.attachment_results = results
        for r in results:
            attempts += 1
            if r.status == "성공":
                success += 1
    return success, attempts


def attachment_status_summary(msg: ProcessedMessage) -> str:
    if not msg.record.has_attachment:
        return "-"
    if not msg.attachment_results:
        return "미처리"
    statuses = [r.status for r in msg.attachment_results]
    if all(s == "성공" for s in statuses):
        return "성공"
    if any(s == "성공" for s in statuses):
        return "부분성공"
    if all(s == "미발견" for s in statuses):
        return "미발견"
    return " / ".join(statuses)
