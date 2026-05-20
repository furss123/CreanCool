"""Gemini categorization and action summarization (키워드 보조 포함)."""

from __future__ import annotations

import json
import re
import time
from typing import Callable, Optional

import config
from src.keyword_classifier import (
    format_hint,
    heuristic_summary,
    predict,
    should_auto_classify,
    should_override_etc,
)
from src.models import ClassificationResult, MessageRecord

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None  # type: ignore
    types = None  # type: ignore


def build_system_instruction() -> str:
    category_lines = "\n".join(
        f'{i + 1}) {c["label"]} — {c["description"]}'
        for i, c in enumerate(config.CATEGORIES)
    )
    labels_json = json.dumps(config.CATEGORY_LABELS, ensure_ascii=False)
    return f"""당신은 한국 고등학교 교사의 쿨메신저(쪽지) 업무 분류 전문가입니다.
제목과 본문 전체를 꼼꼼히 읽고, 교사 업무 관점에서 **가장 적합한 카테고리 하나**를 고르세요.

## 카테고리 (반드시 아래 라벨 문자열과 완전히 일치)
{category_lines}

## 분류 원칙 (매우 중요)
1. **[기타]는 최후의 수단**입니다. 친목·인사·감사·사적 대화처럼 **업무 지시·제출·참석·일정·행정 처리가 전혀 없을 때만** [기타]를 쓰세요.
2. 날짜·시간·장소·행사·대회·시험·학사일정·개학·방학 안내는 **[주요 일정]**을 우선 검토하세요.
3. 성적·평가·나이스·학생부·입력·채점은 **[평가·학력]**입니다.
4. 출결·담임·학급·상담·위클래스·조퇴·학생 생활은 **[생활·학급]**입니다.
5. 교무회의·공문·연수·시간표·복무·교직원 전체 안내는 **[교무·행정]**입니다.
6. 에듀파인·예산·구매·비품·노트북·태블릿 대여는 **[예산·물품]**입니다.
7. 제목만 보지 말고 **본문 전체(줄바꿈·첨부 안내·기한·장소)**를 근거로 판단하세요.
8. 여러 카테고리가 겹치면, 교사가 **당장 해야 할 핵심 업무**에 더 가까운 쪽을 선택하세요.

## 출력
- JSON만 출력: {{"category_label": "...", "action_summary": "..."}}
- category_label 허용 값: {labels_json}
- action_summary: 제출 기한·장소·대상·해야 할 일을 1~2문장으로 명확히 (한국어)"""


VALID_LABELS = set(config.CATEGORY_LABELS)

LABEL_ALIASES: dict[str, str] = {
    "평가·학력": "[평가·학력]",
    "평가": "[평가·학력]",
    "생활·학급": "[생활·학급]",
    "생활": "[생활·학급]",
    "교무·행정": "[교무·행정]",
    "교무": "[교무·행정]",
    "행정": "[교무·행정]",
    "예산·물품": "[예산·물품]",
    "예산": "[예산·물품]",
    "주요 일정": "[주요 일정]",
    "일정": "[주요 일정]",
    "학사일정": "[주요 일정]",
    "기타": "[기타]",
}


def _truncate(text: str, max_len: int = 8000) -> str:
    text = text or ""
    if len(text) <= max_len:
        return text
    return text[: max_len - 50] + "\n...(이하 생략)"


def _parse_json_response(text: str) -> dict:
    text = (text or "").strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            return json.loads(m.group(0))
        raise


def _normalize_label(label: str) -> str:
    label = (label or "").strip()
    if label in VALID_LABELS:
        return label
    if label in LABEL_ALIASES:
        return LABEL_ALIASES[label]
    for valid in config.CATEGORY_LABELS:
        if valid in label or label.replace(" ", "") in valid.replace(" ", ""):
            return valid
    for key, mapped in LABEL_ALIASES.items():
        if key in label:
            return mapped
    return "[기타]"


def _merge_classification(
    llm: ClassificationResult,
    record: MessageRecord,
) -> ClassificationResult:
    """LLM 결과를 키워드 분석으로 보정."""
    pred = predict(record)
    if llm.error and pred.label != "[기타]":
        return ClassificationResult(
            category_label=pred.label,
            action_summary=heuristic_summary(record),
            error=None,
        )
    if llm.category_label == "[기타]" and should_override_etc(pred):
        return ClassificationResult(
            category_label=pred.label,
            action_summary=llm.action_summary or heuristic_summary(record),
            error=llm.error,
        )
    return llm


class GeminiClassifier:
    def __init__(
        self,
        api_key: str,
        model: str = config.DEFAULT_GEMINI_MODEL,
    ):
        if not api_key:
            raise ValueError("Gemini API Key가 필요합니다.")
        if genai is None:
            raise ImportError(
                "google-genai 패키지가 설치되지 않았습니다. pip install google-genai"
            )
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self._system = build_system_instruction()

    def _generate(self, user_prompt: str, *, json_mode: bool) -> str:
        cfg_kwargs: dict = {
            "system_instruction": self._system,
            "temperature": 0.1,
        }
        if json_mode:
            cfg_kwargs["response_mime_type"] = "application/json"
        response = self.client.models.generate_content(
            model=self.model,
            contents=user_prompt,
            config=types.GenerateContentConfig(**cfg_kwargs),
        )
        return response.text or ""

    def classify_one(self, record: MessageRecord) -> ClassificationResult:
        pred = predict(record)
        if should_auto_classify(pred):
            return ClassificationResult(
                category_label=pred.label,
                action_summary=heuristic_summary(record),
            )

        hint = format_hint(pred)
        user_prompt = (
            f"방향: {record.direction}\n"
            f"상대: {record.counterpart}\n"
            f"제목: {record.title}\n"
            f"날짜/시간: {record.datetime_raw}\n"
            f"내용:\n{_truncate(record.content)}\n"
        )
        if hint:
            user_prompt += f"\n---\n{hint}\n(위 힌트를 참고하되, 본문 근거로 최종 판단하세요.)\n"

        last_err: Optional[Exception] = None
        llm_result = ClassificationResult("[기타]", "(AI 분류 실패)", None)
        for json_mode in (True, False):
            try:
                raw = self._generate(user_prompt, json_mode=json_mode)
                data = _parse_json_response(raw)
                label = _normalize_label(data.get("category_label", "[기타]"))
                summary = str(data.get("action_summary", "")).strip()
                llm_result = ClassificationResult(
                    category_label=label, action_summary=summary
                )
                break
            except Exception as e:
                last_err = e
        else:
            llm_result = ClassificationResult(
                category_label="[기타]",
                action_summary="(AI 분류 실패 — 수동 확인 필요)",
                error=str(last_err),
            )

        return _merge_classification(llm_result, record)

    def classify_batch(
        self,
        records: list[MessageRecord],
        progress_callback: Optional[Callable[[int, int], None]] = None,
        delay_seconds: float = 0.3,
    ) -> list[ClassificationResult]:
        results: list[ClassificationResult] = []
        total = len(records)
        for i, rec in enumerate(records):
            results.append(self.classify_one(rec))
            if progress_callback:
                progress_callback(i + 1, total)
            if delay_seconds and i < total - 1:
                time.sleep(delay_seconds)
        return results
