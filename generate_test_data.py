"""쿨메신저 형식 테스트 CSV 및 샘플 첨부파일 생성."""

from __future__ import annotations

import csv
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TEST_DIR = ROOT / "test_data"
ATTACH_DIR = TEST_DIR / "attachments"


def _write_csv(path: Path, columns: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(columns)
        writer.writerows(rows)


def _make_attachments() -> list[str]:
    ATTACH_DIR.mkdir(parents=True, exist_ok=True)
    files = [
        ("성적입력_안내.hwp", "지필평가 성적 입력 안내 (테스트)"),
        ("출결보고서.xlsx", "3학년 2반 출결 현황 (테스트)"),
        ("교무회의_공문.pdf", "5월 전체 교무회의 안내 (테스트)"),
        ("노트북대여_신청서.docx", "태블릿 대여 신청 양식 (테스트)"),
    ]
    for name, body in files:
        (ATTACH_DIR / name).write_text(body, encoding="utf-8")
    return [n for n, _ in files]


def main() -> None:
    today = datetime.now()
    d = lambda offset: (today + timedelta(days=offset)).strftime("%Y-%m-%d %H:%M")

    attach_names = _make_attachments()

    received_cols = ["보낸사람", "제목", "날짜/시간", "내용", "첨부파일"]
    received_rows = [
        [
            "교무기획부 김선생",
            "6월 지필평가 성적 입력",
            d(0),
            "6월 2차 지필평가 성적을 나이스에 입력해 주세요.\n입력 기한: 5월 28일(수) 17:00\n대상: 2학년 전 교과",
            attach_names[0],
        ],
        [
            "담임 박선생",
            "3-2반 조퇴 학생 보고",
            d(-1),
            "오늘 3-2반 김OO 학생 조퇴(14:30) 처리 부탁드립니다.\n위클래스 상담 기록도 확인 바랍니다.",
            attach_names[1],
        ],
        [
            "교장실",
            "전체 교무회의 안내",
            d(-2),
            "5월 22일(목) 16:00 교무실\n전체 교무회의 — 학사 일정 및 체육대회 논의",
            attach_names[2],
        ],
        [
            "교무기획부",
            "6월 학사일정 안내",
            d(1),
            "6월 주요 일정\n- 6/2 개학식\n- 6/10~14 지필고사\n- 6/20 체육대회\n일시·장소는 첨부 참고",
            "",
        ],
        [
            "행정실",
            "노트북 대여 신청",
            d(-3),
            "수업용 노트북 5대 대여 신청서 제출 요청\n에듀파인 기안 후 행정실 방문",
            attach_names[3],
        ],
        [
            "동료 교사 이선생",
            "점심 같이 드실 분",
            d(-5),
            "내일 12시 3층 교실에서 간단히 먹어요~",
            "",
        ],
    ]

    sent_cols = ["받은사람", "제목", "날짜/시간", "내용", "첨부파일"]
    sent_rows = [
        [
            "교무기획부",
            "수행평가 결과 제출",
            d(-1),
            "1학년 국어 수행평가 채점표 첨부합니다.\n확인 부탁드립니다.",
            attach_names[0],
        ],
        [
            "3-2반 학생 김OO",
            "체육대회 참가 명단",
            d(-4),
            "3-2반 체육대회 참가 학생 명단 공유드립니다.",
            "",
        ],
    ]

    _write_csv(TEST_DIR / "받은메시지.csv", received_cols, received_rows)
    _write_csv(TEST_DIR / "보낸메시지.csv", sent_cols, sent_rows)

    try:
        import pandas as pd

        pd.DataFrame(received_rows, columns=received_cols).to_excel(
            TEST_DIR / "받은메시지.xlsx", index=False, engine="openpyxl"
        )
        pd.DataFrame(sent_rows, columns=sent_cols).to_excel(
            TEST_DIR / "보낸메시지.xlsx", index=False, engine="openpyxl"
        )
        xlsx_note = "받은메시지.xlsx, 보낸메시지.xlsx"
    except ImportError:
        xlsx_note = "(openpyxl 미설치 — xlsx 생략)"

    print(f"생성 완료: {TEST_DIR}")
    print(f"  - {TEST_DIR / '받은메시지.csv'}")
    print(f"  - {TEST_DIR / '보낸메시지.csv'}")
    print(f"  - {xlsx_note}")
    print(f"  - 첨부 샘플 {len(attach_names)}개 → {ATTACH_DIR}")
    print()
    print("앱 테스트 시 첨부폴더에 아래 경로를 입력하세요:")
    print(f"  {ATTACH_DIR.resolve()}")


if __name__ == "__main__":
    main()
    sys.exit(0)
