"""분석 결과 DataFrame 후처리(기한·중복)."""

from __future__ import annotations

import pandas as pd

from src import duplicate_finder, task_tracker

ENRICHED_COLUMNS = (
    "message_id",
    "deadline",
    "deadline_display",
    "dup_group",
    "dup_count",
)


def is_enriched(df: pd.DataFrame) -> bool:
    if df is None or df.empty:
        return True
    return all(col in df.columns for col in ENRICHED_COLUMNS)


def ensure_enriched(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    if is_enriched(df):
        out = df.copy()
        return out.drop(columns=["urgency", "completed"], errors="ignore")
    return enrich_dataframe(df)


def enrich_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    out = task_tracker.enrich_tasks(df)
    out = duplicate_finder.assign_duplicate_groups(out)
    return out.drop(columns=["urgency", "completed"], errors="ignore")
