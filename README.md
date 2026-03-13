# JDHE(한국교양교육학회) 논문 리서치 AI (Gemini RAG)

본 프로젝트는 한국교양교육학회(JDHE)의 학술 논문 데이터를 기반으로 정량적 통계 및 정성적 의미 검색을 지원하는 **Hybrid RAG (Retrieval-Augmented Generation)** 시스템입니다. 사용자는 Streamlit 기반의 채팅 인터페이스를 통해 논문 메타데이터와 요약 문구를 자유롭게 질의할 수 있습니다.

## 주요 기능
- **통계적 질문 분석 (Text-to-SQL)**: "Vol 13 Issue 4에 출판된 논문 수는 몇 개인가요?"와 같은 정량적 질문을 SQL로 변환하여 SQLite 데이터베이스에서 정확한 수치를 검색합니다.
- **의미 기반 검색 (Vector Search)**: "다문화 교육에 관한 논문의 핵심 결론을 요약해줘."와 같은 정성적 질문에 대해 ChromaDB 벡터 탐색을 수행하여 관련 논문을 찾아냅니다.
- **Gemini Pro 모델 연동**: Google Gemini 모델을 활용하여 질문 의도를 파악(라우팅)하고, 최종적으로 자연스러운 문장의 답변을 생성합니다.
- **스트리밍 반응형 UI**: Streamlit 챗 인터페이스에 생각하는 과정과 데이터(표, 차트)를 실시간으로 렌더링합니다.
- **사용자 인증 시스템**: FastAPI 기반의 JWT 토큰 인증을 통해 사용자별 독립적인 대화 기록(Session)을 관리합니다.

## 시스템 아키텍처
* **Frontend**: `Streamlit` (`app.py`) 사용자 인터페이스
* **Backend**: `FastAPI` (`src/api.py`, `src/routes/`) RESTful API 서버
* **Database**:
    * `SQLite3` (`data/metadata.db`): 논문 메타데이터 저장 (연도, 권/호, 저자, 키워드 등)
    * `ChromaDB` (`data/chroma/`): 논문 초록/요약의 임베딩 벡터 저장
    * `SQLite3` (`data/conversations.db`): 사용자 채팅 내역 기록
* **LLM**: Google Gemini (`generativeai`)

## 로컬 실행 방법

### 1. 환경 변수 설정
프로젝트 최상단 디렉토리에 `.env` 파일을 생성하고 다음 값을 입력합니다. (이 파일은 Git에 포함되지 않습니다)
```env
GEMINI_API_KEY=당신의_제미나이_API_키
```

### 2. 패키지 설치
UV 패키지 매니저를 사용하여 의존성을 설치합니다.
```bash
uv sync
```

### 3. 서버 실행
터미널 창을 두 개 열어 Backend(FastAPI)와 Frontend(Streamlit)를 각각 구동합니다.

**터미널 1: FastAPI 서버 (Backend)**
```bash
# 8000 포트에서 백엔드 API 서버를 구동합니다.
uv run uvicorn src.api:app --host 0.0.0.0 --port 8000 --reload
```

**터미널 2: Streamlit 앱 (Frontend)**
```bash
# 8501 포트에서 웹 UI를 구동합니다.
uv run streamlit run app.py
```

### 4. 접속
브라우저를 열고 `http://localhost:8501` 에 접속하여 회원가입 후 시스템을 이용할 수 있습니다.

## 보안 및 데이터 관리 (보안 유의사항)
- `data/` 디렉토리(로컬 DB), `papers/` 디렉토리(PDF 등 원본 데이터), 그리고 `.env` 파일은 데이터 유출 및 보안을 위해 버전 관리 `.gitignore`에 등록되어 GitHub에 업로드되지 않습니다.
- API 키나 비밀번호가 소스 코드 내에 하드코딩되지 않고 오직 환경 변수를 통해서만 주입되도록 설계되었습니다.

---
**Author**: donghwan
