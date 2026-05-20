"""공통 LLM 분류 프롬프트 및 응답 파싱."""

from __future__ import annotations

import json
import re

import config

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

FEW_SHOT = """
## 분류 예시
- "6월 지필평가 성적 나이스 입력" → [평가·학력]
- "3-2반 김OO 조퇴 보고" → [생활·학급]
- "전체 교무회의 5/22 16시" → [교무·행정]
- "노트북 대여 에듀파인 기안" → [예산·물품]
- "6월 학사일정 및 체육대회 일정" → [주요 일정]
- "점심 같이 드실 분" → [기타]
"""


def build_system_instruction() -> str:
    category_lines = "\n".join(
        f'- {c["label"]}: {c["description"]}' for c in config.CATEGORIES
    )
    labels_json = json.dumps(config.CATEGORY_LABELS, ensure_ascii=False)
    return f"""당신은 한국 고등학교 교사의 쿨메신저(쪽지) 업무 분류 전문가입니다.
제목과 본문 전체를 꼼꼼히 읽고 교사 업무 관점에서 **가장 적합한 카테고리 하나**만 선택하세요.

## 카테고리
{category_lines}

## 분류 원칙
1. **[기타]는 최후 수단** — 업무 지시·제출·참석·일정·행정 처리가 전혀 없는 친목·인사만 해당.
2. 제목만 보지 말고 **본문 전체**(줄바꿈·첨부·기한·장소)를 근거로 판단.
3. 여러 카테고리가 겹치면 **당장 해야 할 핵심 업무**에 가까운 쪽 선택.
4. "안내", "공지"만으로 [기타]에 넣지 말 것 — 내용에 따라 교무·일정·평가 등으로 분류.
5. 날짜·시간·장소·행사·대회·시험·학사일정 → **[주요 일정]** 우선 검토.

{FEW_SHOT}

## 출력 (JSON만)
{{"category_label": "...", "action_summary": "..."}}
- category_label: 반드시 다음 중 하나 — {labels_json}
- action_summary: 제출 기한·장소·대상·해야 할 일 1~2문장 (한국어)"""


def parse_json_response(text: str) -> dict:
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


def normalize_label(label: str) -> str:
    label = (label or "").strip()
    valid = set(config.CATEGORY_LABELS)
    if label in valid:
        return label
    if label in LABEL_ALIASES:
        return LABEL_ALIASES[label]
    for v in config.CATEGORY_LABELS:
        if v in label or label.replace(" ", "") in v.replace(" ", ""):
            return v
    for key, mapped in LABEL_ALIASES.items():
        if key in label:
            return mapped
    return "[기타]"
