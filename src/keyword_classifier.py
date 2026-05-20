"""키워드·패턴 기반 카테고리 보조 분류 (LLM 보완)."""

from __future__ import annotations

import re
from dataclasses import dataclass

import config
from src.models import MessageRecord

# (키워드, 가중치) — 긴 키워드·고유 용어일수록 높은 점수
CATEGORY_PATTERNS: dict[str, list[tuple[str, int]]] = {
    "[평가·학력]": [
        ("수행평가", 3),
        ("지필평가", 3),
        ("성적입력", 3),
        ("성적 입력", 3),
        ("나이스", 3),
        ("neis", 3),
        ("학생부", 3),
        ("기재", 2),
        ("채점", 2),
        ("성적", 2),
        ("평가", 2),
        ("입력기한", 2),
        ("교과", 1),
    ],
    "[생활·학급]": [
        ("학교폭력", 3),
        ("위클래스", 3),
        ("출결", 3),
        ("조퇴", 3),
        ("외출", 2),
        ("지각", 2),
        ("결석", 2),
        ("담임", 2),
        ("학급", 2),
        ("상담", 2),
        ("생활지도", 2),
        ("체육대회", 2),
        ("학부모", 1),
        ("보호자", 1),
    ],
    "[교무·행정]": [
        ("교무회의", 4),
        ("전체교무", 3),
        ("전체 교무", 3),
        ("공문", 3),
        ("회의", 2),
        ("연수", 3),
        ("시간표", 3),
        ("초과근무", 3),
        ("복무", 2),
        ("교직원", 2),
        ("인사", 2),
        ("발령", 2),
        ("교무", 2),
        ("행정", 1),
        ("공지", 1),
    ],
    "[예산·물품]": [
        ("에듀파인", 3),
        ("교단환경", 3),
        ("예산", 3),
        ("구매", 2),
        ("비품", 2),
        ("노트북", 2),
        ("태블릿", 2),
        ("기기대여", 2),
        ("지출", 2),
        ("결의", 2),
        ("물품", 1),
    ],
    "[주요 일정]": [
        ("학사일정", 5),
        ("학사 일정", 5),
        ("주요 일정", 4),
        ("주요일정", 4),
        ("행사일정", 3),
        ("시험일정", 3),
        ("개학", 3),
        ("방학", 3),
        ("학년도", 2),
        ("일정안내", 3),
        ("일정 안내", 3),
        ("대회", 2),
        ("행사", 2),
        ("개최", 2),
        ("참가", 2),
        ("기간:", 2),
        ("일시:", 2),
        ("월일", 2),
        ("월 ", 1),
        ("일 ", 1),
        ("시 ", 1),
    ],
}

# 기타로 보내기 쉬운 비업무·친목 표현
PERSONAL_HINTS = (
    "점심",
    "저녁",
    "커피",
    "친목",
    "사교",
    "고맙",
    "감사합니다",
    "수고",
    "안녕하세요",
    "생일",
    "축하",
)

AUTO_LABEL_SCORE = 4
OVERRIDE_ETC_SCORE = 2


@dataclass
class KeywordPrediction:
    label: str
    score: int
    scores: dict[str, int]


def _normalize_text(record: MessageRecord) -> str:
    return f"{record.title} {record.content}".lower().replace("\n", " ")


def score_categories(text: str) -> dict[str, int]:
    scores: dict[str, int] = {cat["label"]: 0 for cat in config.CATEGORIES}
    for label, patterns in CATEGORY_PATTERNS.items():
        for keyword, weight in patterns:
            if keyword.lower() in text:
                scores[label] = scores.get(label, 0) + weight
    # 날짜·시간 패턴이 있으면 주요 일정 가산
    if re.search(r"\d{1,2}\s*월\s*\d{1,2}\s*일", text):
        scores["[주요 일정]"] = scores.get("[주요 일정]", 0) + 2
    if re.search(r"\d{1,2}:\d{2}", text):
        scores["[주요 일정]"] = scores.get("[주요 일정]", 0) + 1
    if re.search(r"\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2}", text):
        scores["[주요 일정]"] = scores.get("[주요 일정]", 0) + 2
    return scores


def predict(record: MessageRecord) -> KeywordPrediction:
    text = _normalize_text(record)
    scores = score_categories(text)
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    best_label, best_score = ranked[0]

    if best_score == 0:
        return KeywordPrediction("[기타]", 0, scores)

    # 1위와 2위 점수 차가 작으면 기타 대신 LLM에 맡김 (낮은 신뢰)
    if len(ranked) > 1 and ranked[1][1] > 0:
        if best_score - ranked[1][1] <= 1:
            return KeywordPrediction("[기타]", 0, scores)

    if any(h in text for h in PERSONAL_HINTS) and best_score < 3:
        return KeywordPrediction("[기타]", 0, scores)

    return KeywordPrediction(best_label, best_score, scores)


def should_auto_classify(pred: KeywordPrediction) -> bool:
    return pred.label != "[기타]" and pred.score >= AUTO_LABEL_SCORE


def should_override_etc(pred: KeywordPrediction) -> bool:
    return pred.label != "[기타]" and pred.score >= OVERRIDE_ETC_SCORE


def heuristic_summary(record: MessageRecord) -> str:
    """LLM 없이 키워드만으로 분류할 때 짧은 요약."""
    lines = [ln.strip() for ln in (record.content or "").splitlines() if ln.strip()]
    body = lines[0][:120] if lines else ""
    if body:
        return f"{record.title} — {body}"
    return record.title or "(내용 없음)"


def format_hint(pred: KeywordPrediction) -> str:
    if pred.score <= 0:
        return ""
    top = sorted(pred.scores.items(), key=lambda x: x[1], reverse=True)[:3]
    parts = [f"{lbl}({sc})" for lbl, sc in top if sc > 0]
    return f"키워드 분석: {', '.join(parts)} → **{pred.label}** 후보 (신뢰도 {pred.score})"
