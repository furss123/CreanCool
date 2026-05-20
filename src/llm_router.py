"""Gemini / GPT / Claude 통합 분류."""

from __future__ import annotations

import time
from typing import Callable, Optional

import config
from src import llm_prompts
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
    from google.genai import types as genai_types
except ImportError:
    genai = None  # type: ignore
    genai_types = None  # type: ignore

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None  # type: ignore

try:
    import anthropic
except ImportError:
    anthropic = None  # type: ignore


def _truncate(text: str, max_len: int = 8000) -> str:
    text = text or ""
    if len(text) <= max_len:
        return text
    return text[: max_len - 50] + "\n...(이하 생략)"


def _build_user_prompt(record: MessageRecord, extra_hint: str = "") -> str:
    pred = predict(record)
    hint = format_hint(pred)
    prompt = (
        f"방향: {record.direction}\n"
        f"상대: {record.counterpart}\n"
        f"제목: {record.title}\n"
        f"날짜/시간: {record.datetime_raw}\n"
        f"내용:\n{_truncate(record.content)}\n"
    )
    if hint:
        prompt += f"\n---\n{hint}\n"
    if extra_hint:
        prompt += f"\n{extra_hint}\n"
    return prompt


class MessageClassifier:
    def __init__(
        self,
        api_key: str,
        provider: str = config.DEFAULT_PROVIDER,
        model: str | None = None,
    ):
        if not api_key:
            raise ValueError("API Key가 필요합니다.")
        provider = provider if provider in config.LLM_PROVIDERS else config.DEFAULT_PROVIDER
        pinfo = config.LLM_PROVIDERS[provider]
        self.provider = provider
        self.model = model or pinfo["default_model"]
        self.api_key = api_key
        self._system = llm_prompts.build_system_instruction()

        if provider == "Gemini" and genai is None:
            raise ImportError("pip install google-genai")
        if provider == "GPT" and OpenAI is None:
            raise ImportError("pip install openai")
        if provider == "Claude" and anthropic is None:
            raise ImportError("pip install anthropic")

        if provider == "Gemini":
            self._gemini = genai.Client(api_key=api_key)
        elif provider == "GPT":
            self._openai = OpenAI(api_key=api_key)
        else:
            self._anthropic = anthropic.Anthropic(api_key=api_key)

    def _call_gemini(self, user_prompt: str) -> str:
        for json_mode in (True, False):
            try:
                cfg = {"system_instruction": self._system, "temperature": 0.1}
                if json_mode:
                    cfg["response_mime_type"] = "application/json"
                r = self._gemini.models.generate_content(
                    model=self.model,
                    contents=user_prompt,
                    config=genai_types.GenerateContentConfig(**cfg),
                )
                return r.text or ""
            except Exception:
                if not json_mode:
                    raise
        return ""

    def _call_gpt(self, user_prompt: str) -> str:
        r = self._openai.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self._system},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        return r.choices[0].message.content or ""

    def _call_claude(self, user_prompt: str) -> str:
        r = self._anthropic.messages.create(
            model=self.model,
            max_tokens=1024,
            system=self._system + "\n반드시 JSON 한 줄 객체로만 답하세요.",
            messages=[{"role": "user", "content": user_prompt}],
            temperature=0.1,
        )
        parts = []
        for block in r.content:
            if hasattr(block, "text"):
                parts.append(block.text)
        return "".join(parts)

    def _call_llm(self, user_prompt: str) -> str:
        if self.provider == "Gemini":
            return self._call_gemini(user_prompt)
        if self.provider == "GPT":
            return self._call_gpt(user_prompt)
        return self._call_claude(user_prompt)

    def _parse_llm(self, raw: str) -> ClassificationResult:
        data = llm_prompts.parse_json_response(raw)
        label = llm_prompts.normalize_label(data.get("category_label", "[기타]"))
        summary = str(data.get("action_summary", "")).strip()
        return ClassificationResult(category_label=label, action_summary=summary)

    def _refine(self, result: ClassificationResult, record: MessageRecord) -> ClassificationResult:
        pred = predict(record)
        if result.error and pred.label != "[기타]":
            return ClassificationResult(
                pred.label, heuristic_summary(record), None
            )
        if result.category_label == "[기타]" and should_override_etc(pred):
            return ClassificationResult(
                pred.label,
                result.action_summary or heuristic_summary(record),
                result.error,
            )
        # 기타인데 키워드 1위 점수가 2 이상이면 보정
        if result.category_label == "[기타]" and pred.score >= 2 and pred.label != "[기타]":
            return ClassificationResult(
                pred.label,
                result.action_summary or heuristic_summary(record),
                result.error,
            )
        return result

    def classify_one(self, record: MessageRecord) -> ClassificationResult:
        pred = predict(record)
        if should_auto_classify(pred):
            return ClassificationResult(pred.label, heuristic_summary(record))

        try:
            raw = self._call_llm(_build_user_prompt(record))
            return self._refine(self._parse_llm(raw), record)
        except Exception as e:
            if pred.label != "[기타]" and pred.score >= 1:
                return ClassificationResult(
                    pred.label, heuristic_summary(record), str(e)
                )
            return ClassificationResult(
                "[기타]",
                "(AI 분류 실패 — 수동 확인 필요)",
                str(e),
            )

    def classify_batch(
        self,
        records: list[MessageRecord],
        progress_callback: Optional[Callable[[int, int], None]] = None,
        delay_seconds: float = 0.25,
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
