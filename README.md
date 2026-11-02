# 스터디 할 일·출석 관리

Python, FastAPI, SQLite, HTML/CSS/JavaScript로 만든 로컬 스터디 관리 앱입니다.

## 제공 기능

- 회원가입 및 로그인
- 할 일 추가, 완료, 삭제
- 오늘 출석 체크 및 출석 조회

## 설치

```powershell
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
python -m pip install -r requirements.txt
```

필요하면 `.env.example`을 참고해 `STUDY_SECRET`과 `STUDY_DB_PATH` 환경변수를 설정합니다. 설정하지 않으면 세션 키는 프로세스 시작 시 임시로 생성됩니다.

## 실행

```powershell
uvicorn app.main:app --reload
```

브라우저에서 `http://127.0.0.1:8000`을 엽니다.

## 모델 준비

이 프로젝트는 AI 또는 외부 모델을 사용하지 않습니다. 별도의 모델 다운로드나 모델 파일 준비가 필요하지 않습니다.

## 테스트

```powershell
python -m pytest -q
```

pytest는 회원가입·로그인, 할 일 생명주기, 출석 체크 API를 검증합니다.

## CI

`.github/workflows/ci.yml`은 push와 pull request마다 Python 3.12 가상환경을 만들고 의존성을 설치한 뒤 pytest를 실행합니다.

## Docker

```powershell
docker build -t study-manager .
docker run --rm -p 8000:8000 -e STUDY_SECRET=replace-with-a-random-secret study-manager
```

이후 `http://127.0.0.1:8000`에 접속합니다.
