"""Streamlit UI styles and presentation helpers."""

from __future__ import annotations

import html
from typing import Any

import streamlit as st

import config

# 카테고리별 색상 (배지·카드 좌측 라인)
CATEGORY_THEME: dict[str, dict[str, str]] = {
    "[평가·학력]": {"color": "#1d4ed8", "bg": "#eff6ff", "icon": "📊"},
    "[생활·학급]": {"color": "#047857", "bg": "#ecfdf5", "icon": "🏫"},
    "[교무·행정]": {"color": "#6d28d9", "bg": "#f5f3ff", "icon": "📋"},
    "[예산·물품]": {"color": "#c2410c", "bg": "#fff7ed", "icon": "💼"},
    "[주요 일정]": {"color": "#0e7490", "bg": "#ecfeff", "icon": "📅"},
    "[기타]": {"color": "#475569", "bg": "#f8fafc", "icon": "💬"},
}

DEFAULT_THEME = {"color": "#334155", "bg": "#f1f5f9", "icon": "📌"}


def inject_global_css() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;600;700&display=swap');

        html, body, [class*="css"] {
            font-family: 'Noto Sans KR', -apple-system, BlinkMacSystemFont, sans-serif;
        }

        .block-container {
            padding-top: 1.5rem;
            padding-bottom: 2rem;
            max-width: 1100px;
        }

        /* 사이드바 */
        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #f8fafc 0%, #eef2f7 100%);
            border-right: 1px solid #e2e8f0;
        }
        section[data-testid="stSidebar"] .block-container {
            padding-top: 1.25rem;
        }
        section[data-testid="stSidebar"] h1,
        section[data-testid="stSidebar"] h2,
        section[data-testid="stSidebar"] h3 {
            font-weight: 600;
            letter-spacing: -0.02em;
        }

        /* 메트릭 카드 */
        div[data-testid="stMetric"] {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 0.75rem 1rem;
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
        }
        div[data-testid="stMetric"] label {
            font-size: 0.8rem !important;
            color: #64748b !important;
            font-weight: 500 !important;
        }
        div[data-testid="stMetric"] [data-testid="stMetricValue"] {
            font-size: 1.75rem !important;
            font-weight: 700 !important;
            color: #0f172a !important;
        }

        /* 탭 */
        .stTabs [data-baseweb="tab-list"] {
            gap: 6px;
            background: transparent;
            border-bottom: 1px solid #e2e8f0;
        }
        .stTabs [data-baseweb="tab"] {
            border-radius: 8px 8px 0 0;
            padding: 0.5rem 1rem;
            font-weight: 500;
        }

        /* 버튼 */
        .stButton > button[kind="primary"] {
            border-radius: 10px;
            font-weight: 600;
            border: none;
            background: linear-gradient(135deg, #1e40af 0%, #1d4ed8 100%);
        }
        .stButton > button[kind="secondary"] {
            border-radius: 10px;
            font-weight: 600;
        }

        /* 업로더·입력 */
        div[data-testid="stFileUploader"] section {
            border-radius: 10px;
            border: 1px dashed #cbd5e1;
            background: #fff;
        }

        /* 데이터프레임 */
        div[data-testid="stDataFrame"] {
            border: 1px solid #e2e8f0;
            border-radius: 10px;
            overflow: hidden;
        }

        /* 커스텀 HTML 카드용 여백 */
        .hero-banner {
            background: linear-gradient(135deg, #1e3a5f 0%, #1d4ed8 55%, #2563eb 100%);
            color: #fff;
            padding: 1.75rem 2rem;
            border-radius: 16px;
            margin-bottom: 1.5rem;
            box-shadow: 0 8px 24px rgba(30, 64, 175, 0.2);
        }
        .hero-banner h1 {
            margin: 0 0 0.35rem 0;
            font-size: 1.65rem;
            font-weight: 700;
            letter-spacing: -0.03em;
        }
        .hero-banner p {
            margin: 0;
            opacity: 0.9;
            font-size: 0.95rem;
        }
        .action-card {
            background: #fff;
            border: 1px solid #e2e8f0;
            border-left: 4px solid var(--accent, #1d4ed8);
            border-radius: 12px;
            padding: 1rem 1.15rem;
            margin-bottom: 0.75rem;
            box-shadow: 0 1px 3px rgba(15, 23, 42, 0.05);
        }
        .action-card .badge {
            display: inline-block;
            font-size: 0.72rem;
            font-weight: 600;
            padding: 0.2rem 0.55rem;
            border-radius: 6px;
            background: var(--badge-bg, #eff6ff);
            color: var(--accent, #1d4ed8);
            margin-bottom: 0.45rem;
        }
        .action-card .title {
            font-size: 1rem;
            font-weight: 600;
            color: #0f172a;
            margin: 0 0 0.35rem 0;
        }
        .action-card .meta {
            font-size: 0.8rem;
            color: #64748b;
            margin: 0 0 0.5rem 0;
        }
        .action-card .summary {
            font-size: 0.92rem;
            color: #334155;
            line-height: 1.55;
            margin: 0;
        }
        .sidebar-section {
            font-size: 0.72rem;
            font-weight: 600;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            color: #64748b;
            margin: 0.5rem 0 0.25rem 0;
        }
        .empty-state {
            text-align: center;
            padding: 2.5rem 1rem;
            color: #64748b;
            background: #f8fafc;
            border-radius: 12px;
            border: 1px dashed #cbd5e1;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_hero() -> None:
    st.markdown(
        """
        <div class="hero-banner">
            <h1>📋 교사 업무 자동화</h1>
            <p>쿨메신저 CSV 분석 · Gemini 분류 · 첨부파일 자동 정리</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def sidebar_section(title: str) -> None:
    st.markdown(f'<p class="sidebar-section">{html.escape(title)}</p>', unsafe_allow_html=True)


def category_theme(label: str) -> dict[str, str]:
    return CATEGORY_THEME.get(label, DEFAULT_THEME)


def render_action_card(row: Any) -> None:
    theme = category_theme(str(row.get("category_label", "[기타]")))
    title = html.escape(str(row.get("제목", "")))
    meta = html.escape(
        f"{row.get('direction', '')} · {row.get('counterpart', '')} · {row.get('날짜/시간', '')}"
    )
    summary = html.escape(str(row.get("action_summary") or "(요약 없음)"))
    badge = html.escape(str(row.get("category_label", "")))
    st.markdown(
        f"""
        <div class="action-card" style="--accent: {theme['color']}; --badge-bg: {theme['bg']};">
            <span class="badge">{theme['icon']} {badge}</span>
            <p class="title">{title}</p>
            <p class="meta">{meta}</p>
            <p class="summary">{summary}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_empty_state(message: str, hint: str = "") -> None:
    hint_html = f"<br><small>{html.escape(hint)}</small>" if hint else ""
    st.markdown(
        f'<div class="empty-state">{html.escape(message)}{hint_html}</div>',
        unsafe_allow_html=True,
    )


def tab_label(cat: dict, count: int) -> str:
    theme = category_theme(cat["label"])
    return f"{theme['icon']} {cat['label'].strip('[]')} ({count})"


def status_badge_html(status: str) -> str:
    colors = {
        "성공": ("#047857", "#ecfdf5"),
        "부분성공": ("#b45309", "#fffbeb"),
        "미발견": ("#b91c1c", "#fef2f2"),
        "미처리": ("#64748b", "#f1f5f9"),
    }
    fg, bg = colors.get(status, ("#475569", "#f8fafc"))
    return (
        f'<span style="background:{bg};color:{fg};padding:2px 8px;'
        f'border-radius:6px;font-size:0.75rem;font-weight:600;">{html.escape(status)}</span>'
    )
