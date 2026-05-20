"""유사·중복 메시지 묶기 및 검색."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

import pandas as pd

SIMILARITY_THRESHOLD = 0.82


def normalize_title(title: str) -> str:
    t = str(title or "").strip().lower()
    t = re.sub(r"\s+", "", t)
    t = re.sub(r"[^\w가-힣]", "", t)
    return t


def title_similarity(a: str, b: str) -> float:
    na, nb = normalize_title(a), normalize_title(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    return SequenceMatcher(None, na, nb).ratio()


def assign_duplicate_groups(df: pd.DataFrame) -> pd.DataFrame:
    """dup_group: 동일 그룹은 같은 양수 정수, 단독은 0."""
    out = df.reset_index(drop=True)
    n = len(out)
    if n == 0:
        out["dup_group"] = []
        out["dup_count"] = []
        return out

    parent = list(range(n))
    titles = out["제목"].astype(str).tolist()

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[rj] = ri

    for i in range(n):
        for j in range(i + 1, n):
            if title_similarity(titles[i], titles[j]) >= SIMILARITY_THRESHOLD:
                union(i, j)

    clusters: dict[int, list[int]] = {}
    for i in range(n):
        clusters.setdefault(find(i), []).append(i)

    dup_group = [0] * n
    dup_count = [1] * n
    gid = 0
    for members in clusters.values():
        if len(members) < 2:
            continue
        gid += 1
        for i in members:
            dup_group[i] = gid
            dup_count[i] = len(members)

    out["dup_group"] = dup_group
    out["dup_count"] = dup_count
    return out


def search_messages(df: pd.DataFrame, query: str) -> pd.DataFrame:
    q = (query or "").strip()
    if not q or df.empty:
        return df
    mask = pd.Series(False, index=df.index)
    for col in ("제목", "내용", "action_summary", "counterpart", "category_label"):
        if col in df.columns:
            mask |= df[col].astype(str).str.contains(q, case=False, na=False)
    return df[mask]


def get_duplicate_clusters(df: pd.DataFrame) -> list[dict[str, Any]]:
    if "dup_group" not in df.columns:
        return []
    clusters: list[dict[str, Any]] = []
    for gid in sorted(df.loc[df["dup_group"] > 0, "dup_group"].unique()):
        sub = df[df["dup_group"] == gid]
        if len(sub) < 2:
            continue
        clusters.append(
            {
                "group_id": int(gid),
                "count": len(sub),
                "title": str(sub.iloc[0]["제목"]),
                "df": sub,
            }
        )
    return clusters
