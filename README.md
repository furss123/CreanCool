# 교사 전용 업무 자동화 (CreanCool)

쿨메신저 CSV·Excel을 분석해 업무를 카테고리별로 분류하고, 첨부파일을 자동 정리하는 Streamlit 앱입니다.

## 주요 기능

- 받은/보낸 메시지 CSV·xls·xlsx 업로드
- Gemini AI 분류·요약 (6개 카테고리 + `[주요 일정]`)
- 검색 · 중복 메시지 묶기 · 날짜 필터(분석 대상 제한)
- 첨부파일 → `output/[카테고리]/` 자동 복사

## 로컬 실행

```powershell
cd c:\CreanCool
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
copy .streamlit\secrets.toml.example .streamlit\secrets.toml
# secrets.toml 에 Gemini API 키·첨부폴더 경로 입력
.\.venv\Scripts\streamlit run app.py
```

## GitHub 연결 (최초 1회)

### 1) Git 설치

[Git for Windows](https://git-scm.com/download/win) 설치 후 PowerShell을 **다시 열기**.

### 2) GitHub에 저장소 만들기

1. https://github.com/new 접속
2. Repository name: `CreanCool` (원하는 이름)
3. **Public** 선택 → Create repository

### 3) 프로젝트 업로드

```powershell
cd c:\CreanCool
git init
git add .
git commit -m "Initial commit: teacher workflow Streamlit app"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/CreanCool.git
git push -u origin main
```

`YOUR_USERNAME`을 본인 GitHub 아이디로 바꾸세요.

### 4) 자동 업로드 스크립트 (Git 설치 후)

```powershell
.\scripts\push_to_github.ps1 -GitHubUser YOUR_USERNAME -RepoName CreanCool
```

## 웹 페이지로 공개 (Streamlit Cloud — 권장)

Streamlit 앱은 **GitHub Pages(정적)** 가 아니라 **Streamlit Community Cloud**에 배포합니다.

1. https://share.streamlit.io/ 로그인 (GitHub 연동)
2. **New app** → Repository: `YOUR_USERNAME/CreanCool`, Branch: `main`, Main file: `app.py`
3. **Advanced settings → Secrets** 에 아래 추가:

| Key | Value |
|-----|--------|
| `gemini_api_key` | Google AI Studio API 키 |
| `gemini_model` | `gemini-1.5-pro` |
| `attach_dir` | (클라우드에서는 비워 두거나, 사용 안 함) |

4. Deploy → URL 예: `https://creancool-xxxxx.streamlit.app`

> 첨부파일 자동 정리는 **본인 PC**에서만 동작합니다(로컬 폴더 필요).

## GitHub Pages (소개용 랜딩)

프로젝트 소개용 정적 페이지: 저장소 **Settings → Pages → Source: Deploy from branch → `/docs`**

- 주소: `https://YOUR_USERNAME.github.io/CreanCool/`

## 보안

- `.streamlit/secrets.toml`, `.user_prefs.json` 은 Git에 올라가지 않습니다.
- API 키를 README·코드에 넣지 마세요.
