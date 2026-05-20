"""키워드·패턴 기반 카테고리 보조 분류 (LLM 보완)."""

from __future__ import annotations

import re
from dataclasses import dataclass

import config
from src.models import MessageRecord

CATEGORY_PATTERNS: dict[str, list[tuple[str, int]]] = {
    "[평가·학력]": [
        ("수행평가", 4),
        ("지필평가", 4),
        ("성적입력", 4),
        ("성적 입력", 4),
        ("성적확인", 3),
        ("나이스", 4),
        ("neis", 4),
        ("학생부", 4),
        ("봉사활동", 3),
        ("세부능력", 3),
        ("기재", 3),
        ("채점", 3),
        ("성적", 3),
        ("평가계획", 3),
        ("평가 계획", 3),
        ("입력기한", 3),
        ("입력 기한", 3),
        ("교과", 2),
        ("강의평가",  2),
    ],
    "[생활·학급]": [
        ("학교폭력", 4),
        ("위클래스", 4),
        ("weeclass", 4),
        ("출결", 4),
        ("조퇴", 4),
        ("외출", 3),
        ("지각", 3),
        ("결석", 3),
        ("담임", 3),
        ("학급", 3),
        ("상담", 3),
        ("생활지도", 3),
        ("생활 지도", 3),
        ("체육대회", 3),
        ("학부모", 2),
        ("보호자", 2),
        ("학생회", 2),
        ("봉사", 2),
    ],
    "[교무·행정]": [
        ("교무회의", 5),
        ("전체교무", 4),
        ("전체 교무", 4),
        ("교무실", 3),
        ("공문", 4),
        ("공문시행", 3),
        ("연수", 4),
        ("직무연수", 4),
        ("시간표", 4),
        ("초과근무", 4),
        ("복무", 3),
        ("교직원", 3),
        ("인사", 3),
        ("발령", 3),
        ("교무", 3),
        ("행정", 2),
        ("공지", 2),
        ("제출", 2),
        ("회람", 2),
        ("기안", 2),
    ],
    "[예산·물품]": [
        ("에듀파인", 5),
        ("교단환경", 4),
        ("예산", 4),
        ("구매", 3),
        ("비품", 3),
        ("노트북", 3),
        ("태블릿", 3),
        ("기기대여", 3),
        ("대여", 2),
        ("지출", 3),
        ("결의", 3),
        ("물품", 2),
        ("지급", 2),
        ("수리", 2),
    ],
    "[주요 일정]": [
        ("학사일정", 6),
        ("학사 일정", 6),
        ("주요 일정", 5),
        ("주요일정", 5),
        ("행사일정", 4),
        ("시험일정", 4),
        ("개학", 4),
        ("방학", 4),
        ("개학식", 4),
        ("졸업", 3),
        ("수능", 3),
        ("모의고사", 3),
        ("일정안내", 4),
        ("일정 안내", 4),
        ("대회", 3),
        ("행사", 3),
        ("개최", 3),
        ("참가", 2),
        ("일시", 2),
        ("장소", 2),
    ],
}

PERSONAL_ONLY = (
    "점심 같이",
    "저녁 같이",
    "커피",
    "친목",
    "사교일",
    "생일 축하",
    "고생하셨",
    "수고하셨",
)

AUTO_LABEL_SCORE = 3
OVERRIDE_ETC_SCORE = 2


@dataclass
class KeywordPrediction:
    label: str
    score: int
    scores: dict[str, int]


def _text_blob(record: MessageRecord) -> tuple[str, str]:
    title = (record.title or "").lower()
    body = (record.content or "").lower()
    return title, body


def score_categories(title: str, body: str) -> dict[str, int]:
    scores: dict[str, int] = {cat["label"]: 0 for cat in config.CATEGORIES}
    full = f"{title} {body}"
    for label, patterns in CATEGORY_PATTERNS.items():
        for keyword, weight in patterns:
            kw = keyword.lower()
            if kw in title:
                scores[label] = scores.get(label, 0) + weight + 1
            elif kw in body:
                scores[label] = scores.get(label, 0) + weight
            elif kw in full:
                scores[label] = scores.get(label, 0) + max(1, weight - 1)

    if re.search(r"\d{1,2}\s*월\s*\d{1,2}\s*일", full):
        scores["[주요 일정]"] = scores.get("[주요 일정]", 0) + 3
    if re.search(r"\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2}", full):
        scores["[주요 일정]"] = scores.get("[주요 일정]", 0) + 2
    if re.search(r"(제출|기한|마감|까지)", full):
        for lbl in ("[평가·학력]", "[교무·행정]", "[예산·물품]"):
            scores[lbl] = scores.get(lbl, 0) + 1
    return scores


def predict(record: MessageRecord) -> KeywordPrediction:
    title, body = _text_blob(record)
    scores = score_categories(title, body)
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    best_label, best_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0

    full = f"{title} {body}"
    if any(p in full for p in PERSONAL_ONLY) and best_score < 4:
        return KeywordPrediction("[기타]", 0, scores)

    if best_score == 0:
        return KeywordPrediction("[기타]", 0, scores)

    if best_score >= 3 and best_score - second_score >= 2:
        return KeywordPrediction(best_label, best_score, scores)

    if best_score >= OVERRIDE_ETC_SCORE and best_score - second_score >= 1:
        return KeywordPrediction(best_label, best_score, scores)

    return KeywordPrediction("[기타]", 0, scores)


def should_auto_classify(pred: KeywordPrediction) -> bool:
    return pred.label != "[기타]" and pred.score >= AUTO_LABEL_SCORE


def should_override_etc(pred: KeywordPrediction) -> bool:
    return pred.label != "[기타]" and pred.score >= OVERRIDE_ETC_SCORE


def heuristic_summary(record: MessageRecord) -> str:
    lines = [ln.strip() for ln in (record.content or "").splitlines() if ln.strip()]
    for line in lines[:5]:
        if any(k in line for k in ("기한", "까지", "제출", "입력", "참석", "일시", "장소")):
            return f"{record.title} — {line[:100]}"
    body = lines[0][:120] if lines else ""
    return f"{record.title} — {body}" if body else (record.title or "(내용 없음)")


def format_hint(pred: KeywordPrediction) -> str:
    if pred.score <= 0:
        return ""
    top = sorted(pred.scores.items(), key=lambda x: x[1], reverse=True)[:3]
    parts = [f"{lbl}({sc})" for lbl, sc in top if sc > 0]
    return f"키워드 분석: {', '.join(parts)} → {pred.label} (신뢰 {pred.score})"
