"""CSV/Excel loading, encoding detection, and message normalization."""

from __future__ import annotations

import csv
import io
import re
from datetime import date, datetime
from pathlib import Path
from typing import BinaryIO, Optional

import chardet
import pandas as pd
from dateutil import parser as date_parser

import config
from src.models import MessageRecord

RECEIVED_RENAME = {"보낸사람": "_counterpart"}
SENT_RENAME = {"받은사람": "_counterpart"}

SUPPORTED_EXTENSIONS = {".csv", ".xls", ".xlsx"}


def detect_encoding(raw: bytes) -> str:
    detected = chardet.detect(raw)
    enc = (detected.get("encoding") or "utf-8").lower()
    if enc in ("ascii", "iso-8859-1") and _looks_korean(raw[:8000]):
        return "cp949"
    return enc


def _looks_korean(sample: bytes) -> bool:
    try:
        text = sample.decode("cp949", errors="ignore")
    except Exception:
        return False
    return bool(re.search(r"[가-힣]", text))


def decode_bytes(raw: bytes) -> tuple[str, str]:
    """Return (text, encoding_used)."""
    for enc in config.ENCODINGS_TO_TRY:
        try:
            return raw.decode(enc), enc
        except (UnicodeDecodeError, LookupError):
            continue
    enc = detect_encoding(raw)
    try:
        return raw.decode(enc, errors="replace"), enc
    except Exception:
        return raw.decode("utf-8", errors="replace"), "utf-8"


def _read_csv_robust_text(text: str, expected_columns: tuple[str, ...]) -> pd.DataFrame:
    """Parse CSV with multiline quoted fields; fall back to manual row merge."""
    buf = io.StringIO(text)
    attempts: list[dict] = [
        {"engine": "python", "quoting": csv.QUOTE_MINIMAL, "on_bad_lines": "warn"},
        {"engine": "python", "quoting": csv.QUOTE_ALL, "on_bad_lines": "warn"},
        {"engine": "c", "quoting": csv.QUOTE_MINIMAL, "on_bad_lines": "skip"},
    ]
    last_err: Optional[Exception] = None
    for kwargs in attempts:
        try:
            buf.seek(0)
            df = pd.read_csv(buf, **kwargs)
            if len(df.columns) >= len(expected_columns):
                return _align_columns(df, expected_columns)
        except Exception as e:
            last_err = e
    buf.seek(0)
    try:
        df = _parse_csv_manual(text, expected_columns)
        return df
    except Exception as e:
        raise ValueError(f"CSV 파싱 실패: {last_err or e}") from e


def _align_columns(df: pd.DataFrame, expected: tuple[str, ...]) -> pd.DataFrame:
    cols = [str(c).strip() for c in df.columns]
    df.columns = cols
    if len(cols) == len(expected) and cols != list(expected):
        mapping = {}
        for i, exp in enumerate(expected):
            if i < len(cols):
                mapping[cols[i]] = exp
        df = df.rename(columns=mapping)
    elif len(cols) > len(expected):
        df = df.iloc[:, : len(expected)]
        df.columns = list(expected)
    elif len(cols) < len(expected):
        raise ValueError(f"컬럼 수 부족: 기대 {len(expected)}, 실제 {len(cols)}")
    else:
        df.columns = list(expected)
    return df.fillna("")


def _parse_csv_manual(text: str, expected_columns: tuple[str, ...]) -> pd.DataFrame:
    """When pandas mis-aligns rows, merge overflow fields into '내용'."""
    reader = csv.reader(io.StringIO(text), quotechar='"', doublequote=True)
    rows = list(reader)
    if not rows:
        raise ValueError("CSV가 비어 있습니다.")
    header = [h.strip() for h in rows[0]]
    n = len(expected_columns)
    if header != list(expected_columns):
        if len(header) == n:
            pass
        else:
            rows[0] = list(expected_columns)
    data_rows: list[list[str]] = []
    for row in rows[1:]:
        if not row or all(not str(c).strip() for c in row):
            continue
        if len(row) == n:
            data_rows.append(row)
        elif len(row) > n:
            fixed = row[:2] + ["\n".join(row[2:-2])] + row[-2:]
            while len(fixed) < n:
                fixed.append("")
            data_rows.append(fixed[:n])
        else:
            padded = row + [""] * (n - len(row))
            data_rows.append(padded)
    return pd.DataFrame(data_rows, columns=list(expected_columns)).fillna("")


def _read_excel_bytes(raw: bytes, filename: str, expected: tuple[str, ...]) -> pd.DataFrame:
    ext = Path(filename).suffix.lower()
    buf = io.BytesIO(raw)
    engine = "xlrd" if ext == ".xls" else "openpyxl"
    try:
        df = pd.read_excel(buf, engine=engine, dtype=str, sheet_name=0)
    except Exception as e:
        raise ValueError(f"Excel 파일을 읽을 수 없습니다 ({filename}): {e}") from e
    df = df.fillna("")
    return _align_columns(df, expected)


def _raw_to_dataframe(
    raw: bytes,
    filename: str,
    expected: tuple[str, ...],
) -> pd.DataFrame:
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"지원하지 않는 형식입니다: {ext} (지원: {', '.join(sorted(SUPPORTED_EXTENSIONS))})"
        )
    if ext in (".xls", ".xlsx"):
        return _read_excel_bytes(raw, filename, expected)
    text, _ = decode_bytes(raw)
    return _read_csv_robust_text(text, expected)


def _finalize_message_df(
    df: pd.DataFrame,
    message_type: str,
    source_name: str,
) -> pd.DataFrame:
    if message_type == "received":
        rename = RECEIVED_RENAME
        direction = "받음"
    else:
        rename = SENT_RENAME
        direction = "보냄"
    df = df.rename(columns=rename)
    df["direction"] = direction
    df["source_file"] = source_name
    df["counterpart"] = df["_counterpart"].astype(str)
    for col in ("제목", "날짜/시간", "내용", "첨부파일"):
        df[col] = df[col].astype(str)
    df["parsed_date"] = df["날짜/시간"].map(parse_message_date)
    return df[
        [
            "direction",
            "counterpart",
            "제목",
            "날짜/시간",
            "내용",
            "첨부파일",
            "parsed_date",
            "source_file",
        ]
    ]


def load_message_upload(
    file_obj: BinaryIO,
    message_type: str,
    source_name: str = "",
) -> pd.DataFrame:
    """
    message_type: 'received' | 'sent'
    Supports .csv, .xls, .xlsx
    """
    name = source_name or getattr(file_obj, "name", "upload.csv")
    raw = file_obj.read()
    if hasattr(file_obj, "seek"):
        file_obj.seek(0)
    if message_type == "received":
        expected = config.RECEIVED_COLUMNS
    else:
        expected = config.SENT_COLUMNS
    df = _raw_to_dataframe(raw, name, expected)
    return _finalize_message_df(df, message_type, name)


def load_csv_upload(
    file_obj: BinaryIO,
    message_type: str,
    source_name: str = "",
) -> pd.DataFrame:
    """하위 호환 alias."""
    return load_message_upload(file_obj, message_type, source_name)


def parse_message_date(value: str) -> Optional[date]:
    if not value or not str(value).strip():
        return None
    s = str(value).strip()
    try:
        dt = date_parser.parse(s, fuzzy=True, dayfirst=False)
        return dt.date()
    except (ValueError, TypeError, OverflowError):
        pass
    m = re.search(r"(\d{4})[.\-/년\s]+(\d{1,2})[.\-/월\s]+(\d{1,2})", s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    return None


def merge_dataframes(dfs: list[pd.DataFrame]) -> pd.DataFrame:
    if not dfs:
        return pd.DataFrame()
    return pd.concat(dfs, ignore_index=True)


def dataframe_to_records(df: pd.DataFrame) -> list[MessageRecord]:
    records: list[MessageRecord] = []
    for _, row in df.iterrows():
        records.append(
            MessageRecord(
                direction=str(row.get("direction", "")),
                counterpart=str(row.get("counterpart", "")),
                title=str(row.get("제목", "")),
                datetime_raw=str(row.get("날짜/시간", "")),
                content=str(row.get("내용", "")),
                attachments_raw=str(row.get("첨부파일", "")),
                parsed_date=row.get("parsed_date"),
                source_file=str(row.get("source_file", "")),
            )
        )
    return records


def filter_by_date_range(
    df: pd.DataFrame,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    *,
    strict: bool = True,
) -> pd.DataFrame:
    """
    strict=True: parsed_date가 기간 안인 행만 (분석용).
    strict=False: 날짜 없는 행도 함께 포함 (구버전 호환).
    """
    if date_from is None and date_to is None:
        return df.copy()
    if "parsed_date" not in df.columns or df.empty:
        return df.iloc[0:0].copy()

    out = df.copy()
    if date_from and date_to and date_from > date_to:
        date_from, date_to = date_to, date_from

    dates = pd.to_datetime(out["parsed_date"], errors="coerce")
    mask = dates.notna() if strict else pd.Series(True, index=out.index)
    if date_from is not None:
        mask &= dates >= pd.Timestamp(date_from)
    if date_to is not None:
        mask &= dates <= pd.Timestamp(date_to)
    return out.loc[mask].copy()


def filter_messages(
    df: pd.DataFrame,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    categories: Optional[list[str]] = None,
    *,
    strict_dates: bool = True,
) -> pd.DataFrame:
    out = df.copy()
    if date_from is not None or date_to is not None:
        out = filter_by_date_range(out, date_from, date_to, strict=strict_dates)
    if categories and "category_label" in out.columns:
        out = out[out["category_label"].isin(categories)]
    return out


def is_today(d: Optional[date]) -> bool:
    if d is None:
        return False
    return d == datetime.now().date()
