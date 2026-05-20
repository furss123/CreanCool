"""
교사 전용 업무 자동화 — Streamlit 진입점.
실행: streamlit run app.py
"""

from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import streamlit as st

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import config
from src import (
    data_processor,
    duplicate_finder,
    file_manager,
    message_enricher,
    settings_store,
    ui_styles,
)
from src.llm_router import MessageClassifier
from src.models import ProcessedMessage

st.set_page_config(
    page_title="교사 업무 자동화",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

ui_styles.inject_global_css()
CATEGORY_OPTIONS = config.CATEGORY_LABELS
UPLOAD_TYPES = ["csv", "xls", "xlsx"]
PROVIDER_LIST = list(config.LLM_PROVIDERS.keys())


def _secret(key: str, default: str = "") -> str:
    try:
        val = st.secrets.get(key, default)
    except (FileNotFoundError, KeyError, AttributeError):
        return default
    return str(val) if val is not None else default


def _default_setting(key: str, secret_key: str, secret_default: str = "") -> str:
    remembered = settings_store.get_field(key, "")
    if remembered:
        return remembered
    return _secret(secret_key, secret_default) or _secret(
        "gemini_api_key" if key == "api_key" else key, secret_default
    )


def _normalize_dir_path(raw: str) -> str:
    return (raw or "").strip().strip('"').strip("'")


def _attach_dir_candidates() -> list[str]:
    candidates: list[str] = []
    for value in (
        st.session_state.get("attach_dir", ""),
        settings_store.get_field("attach_dir", ""),
        _default_setting("attach_dir", "attach_dir"),
        str(_ROOT / "test_data" / "attachments"),
        r"C:\Users\User\Documents\CoolMessenger Files\Received Files",
    ):
        path = _normalize_dir_path(str(value))
        if path and path not in candidates:
            candidates.append(path)
    return candidates


def _ensure_attach_dir_default() -> None:
    current = _normalize_dir_path(st.session_state.get("attach_dir", ""))
    if current and Path(current).is_dir():
        st.session_state.attach_dir = current
        return
    for path in _attach_dir_candidates():
        if Path(path).is_dir():
            st.session_state.attach_dir = path
            return


def _resolve_attach_dir() -> tuple[Path | None, list[str]]:
    tried: list[str] = []
    for path in _attach_dir_candidates():
        if path in tried:
            continue
        tried.append(path)
        p = Path(path)
        if p.is_dir():
            return p, tried
    return None, tried


def _on_provider_change() -> None:
    provider = st.session_state.llm_provider
    st.session_state.llm_model = config.LLM_PROVIDERS[provider]["default_model"]


def _init_session() -> None:
    defaults = {
        "messages_df": None,
        "processed_messages": [],
        "analysis_done": False,
        "files_routed": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
    if "api_key" not in st.session_state:
        st.session_state.api_key = _default_setting("api_key", "api_key") or _default_setting(
            "api_key", "gemini_api_key"
        )
    if "llm_provider" not in st.session_state:
        st.session_state.llm_provider = _default_setting(
            "llm_provider", "llm_provider", config.DEFAULT_PROVIDER
        )
    if "llm_model" not in st.session_state:
        st.session_state.llm_model = _default_setting(
            "llm_model", "llm_model", config.LLM_PROVIDERS[config.DEFAULT_PROVIDER]["default_model"]
        )
    if "attach_dir" not in st.session_state:
        st.session_state.attach_dir = _default_setting("attach_dir", "attach_dir")
    if "remember_settings" not in st.session_state:
        st.session_state.remember_settings = bool(
            settings_store.load_prefs().get("remember")
        )
    _ensure_attach_dir_default()


def _render_top_settings() -> dict:
    """상단 설정 패널."""
    st.markdown("### ⚙️ 설정")
    row1 = st.columns([1, 1.2, 2.2])
    with row1[0]:
        provider = st.selectbox(
            "AI 제공자",
            PROVIDER_LIST,
            key="llm_provider",
            on_change=_on_provider_change,
        )
    pinfo = config.LLM_PROVIDERS[provider]
    models = pinfo["models"]
    if st.session_state.llm_model not in models:
        st.session_state.llm_model = pinfo["default_model"]
    try:
        model_idx = models.index(st.session_state.llm_model)
    except ValueError:
        model_idx = 0
        st.session_state.llm_model = models[0]
    with row1[1]:
        model = st.selectbox(
            "모델",
            models,
            index=model_idx,
            key="llm_model",
        )
    with row1[2]:
        api_key = st.text_input(
            "API Key",
            type="password",
            key="api_key",
            help=f"키 발급: {pinfo['key_url']}",
        )

    row2 = st.columns([2.5, 1, 1])
    with row2[0]:
        attach_dir = st.text_input(
            "첨부파일 폴더 (절대 경로)",
            key="attach_dir",
            placeholder=r"C:\...\CoolMessenger Files\Received Files",
        )
    with row2[1]:
        remember = st.checkbox(
            "설정 기억하기",
            key="remember_settings",
            help="API 키·모델·첨부 경로를 이 PC에 저장",
        )
    with row2[2]:
        attach_path, _ = _resolve_attach_dir()
        if attach_path:
            st.success("첨부 폴더 OK")
        elif _normalize_dir_path(attach_dir):
            st.warning("경로 확인")

    if remember:
        settings_store.save_prefs(
            True,
            st.session_state.api_key,
            st.session_state.llm_provider,
            st.session_state.llm_model,
            st.session_state.attach_dir,
        )
    else:
        settings_store.save_prefs(False)

    st.divider()
    return {
        "api_key": api_key,
        "provider": provider,
        "model": model,
        "attach_dir": attach_dir,
        "remember_settings": remember,
    }


def _records_to_dataframe(messages: list[ProcessedMessage]) -> pd.DataFrame:
    rows = []
    for i, pm in enumerate(messages):
        attach_status = file_manager.attachment_status_summary(pm)
        rows.append(
            {
                "idx": i,
                "direction": pm.record.direction,
                "counterpart": pm.record.counterpart,
                "제목": pm.record.title,
                "날짜/시간": pm.record.datetime_raw,
                "parsed_date": pm.record.parsed_date,
                "내용": pm.record.content,
                "첨부파일": pm.record.attachments_raw,
                "category_label": pm.classification.category_label,
                "action_summary": pm.classification.action_summary,
                "ai_error": pm.classification.error or "",
                "attach_status": attach_status,
                "source_file": pm.record.source_file,
            }
        )
    return pd.DataFrame(rows)


def _refresh_dataframe() -> None:
    df = _records_to_dataframe(st.session_state.processed_messages)
    st.session_state.messages_df = message_enricher.enrich_dataframe(df)


def _load_uploaded_files(received_file, sent_file) -> pd.DataFrame:
    dfs = []
    if received_file is not None:
        dfs.append(
            data_processor.load_message_upload(
                received_file, "received", received_file.name
            )
        )
    if sent_file is not None:
        dfs.append(
            data_processor.load_message_upload(sent_file, "sent", sent_file.name)
        )
    return data_processor.merge_dataframes(dfs)


def _run_analysis(
    api_key: str,
    provider: str,
    model: str,
    df: pd.DataFrame,
) -> list[ProcessedMessage]:
    records = data_processor.dataframe_to_records(df)
    classifier = MessageClassifier(api_key=api_key, provider=provider, model=model)
    progress = st.progress(0, text=f"{provider} · {model} 분류 중...")
    total = len(records)

    def on_progress(done: int, tot: int) -> None:
        progress.progress(done / max(tot, 1), text=f"분류 중... {done}/{tot}")

    classifications = classifier.classify_batch(
        records, progress_callback=on_progress
    )
    progress.empty()
    return [
        ProcessedMessage(record=rec, classification=clf)
        for rec, clf in zip(records, classifications)
    ]


def _apply_filters(
    df: pd.DataFrame,
    date_from: date | None,
    date_to: date | None,
    categories: list[str],
    *,
    use_date_filter: bool = False,
) -> pd.DataFrame:
    if use_date_filter:
        return data_processor.filter_messages(
            df, date_from, date_to, categories or None, strict_dates=True
        )
    return data_processor.filter_messages(
        df, None, None, categories or None, strict_dates=True
    )


def _apply_view_filters(
    df: pd.DataFrame, search_q: str, duplicates_only: bool
) -> pd.DataFrame:
    out = duplicate_finder.search_messages(df, search_q)
    if duplicates_only and "dup_group" in out.columns:
        out = out[out["dup_group"] > 0]
    elif duplicates_only:
        out = out.iloc[0:0]
    return out


def _render_metrics(df: pd.DataFrame) -> None:
    total = len(df)
    today_count = int(
        (df["parsed_date"] == datetime.now().date()).sum()
        if "parsed_date" in df.columns
        else 0
    )
    with_attach = int(
        df["첨부파일"].astype(str).str.strip().replace("nan", "").astype(bool).sum()
    )
    routed_ok = int((df["attach_status"] == "성공").sum())
    etc_count = int((df["category_label"] == "[기타]").sum()) if "category_label" in df.columns else 0

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("전체", f"{total:,}")
    c2.metric("오늘", f"{today_count:,}")
    c3.metric("기타", f"{etc_count:,}")
    c4.metric("첨부", f"{with_attach:,}")
    c5.metric("정리완료", f"{routed_ok:,}")


def _render_search_and_filters(df: pd.DataFrame) -> pd.DataFrame:
    st.markdown("### 🔍 검색 · 필터")
    c1, c2 = st.columns([4, 1])
    with c1:
        search_q = st.text_input(
            "검색 (제목·내용·요약·상대·카테고리)",
            key="search_query",
            placeholder="예: 성적, 체육대회, 연수",
        )
    with c2:
        duplicates_only = st.checkbox("중복·유사만", key="filter_duplicates")
    return _apply_view_filters(df, search_q, duplicates_only)


def _render_duplicate_groups(df: pd.DataFrame) -> None:
    clusters = duplicate_finder.get_duplicate_clusters(df)
    if not clusters:
        return
    st.markdown("### 🔗 중복 · 유사 메시지")
    st.caption(f"제목 유사도 {duplicate_finder.SIMILARITY_THRESHOLD:.0%} 이상 묶음")
    for cl in clusters:
        title_preview = cl["title"][:50] + ("…" if len(cl["title"]) > 50 else "")
        with st.expander(f"그룹 {cl['group_id']} · {cl['count']}건 — {title_preview}"):
            cols = [
                c
                for c in (
                    "제목",
                    "날짜/시간",
                    "counterpart",
                    "category_label",
                    "deadline_display",
                )
                if c in cl["df"].columns
            ]
            st.dataframe(cl["df"][cols], use_container_width=True, hide_index=True)


def _render_category_tabs(df: pd.DataFrame) -> None:
    st.markdown("### 📂 카테고리별 메시지")
    df = message_enricher.ensure_enriched(df)
    tab_defs = [
        (cat, len(df[df["category_label"] == cat["label"]]))
        for cat in config.CATEGORIES
    ]
    tabs = st.tabs([ui_styles.tab_label(c, n) for c, n in tab_defs])
    display_cols = [
        "deadline_display",
        "제목",
        "날짜/시간",
        "action_summary",
        "attach_status",
    ]
    rename_map = {
        "deadline_display": "기한",
        "action_summary": "핵심 액션",
        "attach_status": "첨부",
    }
    for tab, cat in zip(tabs, config.CATEGORIES):
        with tab:
            sub = df[df["category_label"] == cat["label"]]
            theme = ui_styles.category_theme(cat["label"])
            st.markdown(
                f'<p style="color:#64748b;font-size:0.9rem;">'
                f'{theme["icon"]} {cat["description"]}</p>',
                unsafe_allow_html=True,
            )
            if sub.empty:
                ui_styles.render_empty_state("해당 메시지 없음")
                continue
            cols = [c for c in display_cols if c in sub.columns]
            display = sub[cols].rename(
                columns={k: rename_map[k] for k in cols if k in rename_map}
            )
            st.dataframe(display, use_container_width=True, hide_index=True)


def main() -> None:
    _init_session()
    config.ensure_category_dirs()

    ui_styles.render_hero()
    settings = _render_top_settings()
    api_key = settings["api_key"]
    provider = settings["provider"]
    model = settings["model"]

    with st.sidebar:
        st.markdown("### 📁 데이터 · 실행")
        received_file = st.file_uploader("받은메시지 (CSV / Excel)", type=UPLOAD_TYPES)
        sent_file = st.file_uploader("보낸메시지 (CSV / Excel)", type=UPLOAD_TYPES)

        st.divider()
        use_date_filter = st.checkbox(
            "날짜 필터 (분석 대상 제한)",
            value=False,
        )
        date_from_val = date_to_val = None
        if use_date_filter:
            dc1, dc2 = st.columns(2)
            with dc1:
                date_from_val = st.date_input("시작일", value=datetime.now().date())
            with dc2:
                date_to_val = st.date_input("종료일", value=datetime.now().date())

        selected_categories = st.multiselect(
            "결과 카테고리 표시",
            options=CATEGORY_OPTIONS,
            default=CATEGORY_OPTIONS,
        )

        st.divider()
        analyze_btn = st.button(
            "AI 분류 · 요약 실행",
            type="primary",
            use_container_width=True,
            icon="🤖",
        )

    if analyze_btn:
        if not api_key:
            st.error("API Key를 입력해 주세요.")
        elif received_file is None and sent_file is None:
            st.error("파일을 업로드해 주세요.")
        else:
            try:
                with st.spinner("데이터 로드 중..."):
                    raw_df = _load_uploaded_files(received_file, sent_file)
                total_loaded = len(raw_df)
                if raw_df.empty:
                    st.warning("로드된 메시지가 없습니다.")
                else:
                    if use_date_filter and date_from_val and date_to_val:
                        raw_df = data_processor.filter_by_date_range(
                            raw_df, date_from_val, date_to_val, strict=True
                        )
                        if raw_df.empty:
                            st.warning(
                                f"선택 기간({date_from_val}~{date_to_val})에 메시지 없음 "
                                f"(전체 {total_loaded}건)"
                            )
                            return
                        st.info(
                            f"날짜 필터: **{len(raw_df)}건** 분석 (전체 {total_loaded}건)"
                        )
                    processed = _run_analysis(api_key, provider, model, raw_df)
                    st.session_state.processed_messages = processed
                    st.session_state.messages_df = message_enricher.enrich_dataframe(
                        _records_to_dataframe(processed)
                    )
                    st.session_state.analysis_done = True
                    st.session_state.files_routed = False
                    dist = (
                        st.session_state.messages_df["category_label"]
                        .value_counts()
                        .to_dict()
                    )
                    st.toast(f"{len(processed)}건 분석 ({provider})", icon="✅")
                    st.caption(
                        "분포: " + " · ".join(f"{k} {v}" for k, v in dist.items())
                    )
            except Exception as e:
                st.exception(e)

    df: pd.DataFrame | None = st.session_state.messages_df
    if df is None or df.empty:
        ui_styles.render_empty_state(
            "아직 분석된 데이터가 없습니다.",
            "CSV·Excel 업로드 후 「AI 분류 · 요약 실행」을 눌러 주세요.",
        )
        return

    df = message_enricher.ensure_enriched(df)
    st.session_state.messages_df = df

    filtered = _apply_filters(
        df,
        date_from_val,
        date_to_val,
        selected_categories,
        use_date_filter=use_date_filter,
    )
    view_df = _render_search_and_filters(filtered)

    _render_metrics(view_df)
    _render_category_tabs(view_df)

    st.markdown("---")
    _render_duplicate_groups(view_df)

    st.markdown("---")
    col_btn, col_info = st.columns([1, 2])
    with col_btn:
        route_btn = st.button(
            "첨부파일 자동 정리",
            type="secondary",
            use_container_width=True,
            icon="📁",
        )
    with col_info:
        st.caption(f"출력: `{config.get_output_dir()}`")

    if route_btn:
        attach_path, tried_paths = _resolve_attach_dir()
        if attach_path is None:
            st.error("유효한 첨부파일 폴더 경로를 입력해 주세요.")
            if tried_paths:
                st.caption("확인: " + " | ".join(f"`{p}`" for p in tried_paths))
        else:
            try:
                messages = st.session_state.processed_messages
                idx_map = {i: pm for i, pm in enumerate(messages)}
                subset = [
                    idx_map[i]
                    for i in view_df["idx"].tolist()
                    if i in idx_map
                ]
                success, attempts = file_manager.route_all_attachments(
                    subset, str(attach_path)
                )
                _refresh_dataframe()
                st.toast(f"첨부 {success}/{attempts}건 복사", icon="📁")
            except Exception as e:
                st.exception(e)


if __name__ == "__main__":
    main()
