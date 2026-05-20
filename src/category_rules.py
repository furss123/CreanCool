"""카테고리 수동 수정 및 키워드 규칙 저장."""

from __future__ import annotations

import json
from typing import Any

import config
from src.models import ClassificationResult, ProcessedMessage

RULES_FILE = config.get_base_dir() / ".category_rules.json"


def load_rules() -> list[dict[str, str]]:
    if not RULES_FILE.exists():
        return []
    try:
        data = json.loads(RULES_FILE.read_text(encoding="utf-8"))
        rules = data.get("rules", []) if isinstance(data, dict) else data
        if isinstance(rules, list):
            return [r for r in rules if isinstance(r, dict) and r.get("keyword")]
    except (json.JSONDecodeError, OSError):
        pass
    return []


def save_rules(rules: list[dict[str, str]]) -> None:
    try:
        RULES_FILE.write_text(
            json.dumps({"rules": rules}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass


def add_rule(keyword: str, category_label: str) -> list[dict[str, str]]:
    keyword = keyword.strip()
    if not keyword or category_label not in config.CATEGORY_LABELS:
        return load_rules()
    rules = load_rules()
    rules = [r for r in rules if r.get("keyword") != keyword]
    rules.append({"keyword": keyword, "category": category_label})
    save_rules(rules)
    return rules


def remove_rule(keyword: str) -> list[dict[str, str]]:
    rules = [r for r in load_rules() if r.get("keyword") != keyword]
    save_rules(rules)
    return rules


def match_rule(text: str, rules: list[dict[str, str]]) -> str | None:
    text = text or ""
    for rule in rules:
        kw = rule.get("keyword", "")
        if kw and kw in text:
            cat = rule.get("category", "")
            if cat in config.CATEGORY_LABELS:
                return cat
    return None


def apply_rules_to_processed(messages: list[ProcessedMessage]) -> int:
    """규칙 적용 건수 반환."""
    rules = load_rules()
    if not rules:
        return 0
    count = 0
    for pm in messages:
        text = f"{pm.record.title} {pm.record.content}"
        matched = match_rule(text, rules)
        if matched:
            pm.classification = ClassificationResult(
                category_label=matched,
                action_summary=pm.classification.action_summary,
                error=pm.classification.error,
            )
            count += 1
    return count


def update_message_category(
    messages: list[ProcessedMessage],
    idx: int,
    new_label: str,
) -> None:
    if 0 <= idx < len(messages):
        pm = messages[idx]
        pm.classification = ClassificationResult(
            category_label=new_label,
            action_summary=pm.classification.action_summary,
            error=pm.classification.error,
        )
