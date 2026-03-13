import os
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import Optional, List

# Load environment variables
load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY가 설정되지 않았습니다. .env 파일에 추가해주세요.")


MODEL_NAME = 'gemini-2.5-flash'

# Database Settings
SQLITE_DB_PATH = 'data/metadata.db'
CHROMA_DB_PATH = 'data/chroma_db'

# Extraction Schema (FR1)
class Methodology(BaseModel):
    type: str = Field(description="연구 접근 유형 (예: 질적 연구, 양적 연구, 혼합방법 연구, 문헌분석/리뷰 등)")
    details: str = Field(description="구체적 연구 방법 (구체적 방법이 없으면 '미상/명시 없음')")

class Participants(BaseModel):
    description: str = Field(description="연구 참여자의 전반적인 설명, 인구통계학적 배경 등")
    target_groups_array: List[str] = Field(description="연구 대상자 그룹의 배열 형식 분류")
    sample_size_integer: int = Field(description="총 표본 크기 숫자")

class PaperMetadata(BaseModel):
    document_id: str = Field(description="PDF 파일명 또는 논문 고유 식별자 (예: JDHE_V18_I3_01)")
    title: str = Field(description="논문 제목")
    publication_year: int = Field(description="게재 연도 숫자 (예: 2024)")
    volume: str = Field(description="Volume 번호")
    issue: str = Field(description="Issue 번호")
    research_topic: str = Field(description="이 논문이 다루는 핵심 문제와 목적 요약")
    theoretical_framework: str = Field(description="이 연구를 지탱하는 핵심 이론적 배경이나 렌즈 (없으면 '명시 없음')")
    methodology: Methodology
    data_collection_method: str = Field(description="표집 방법 및 데이터 수집 절차(설문조사, 인터뷰, 관찰 등)")
    data_analysis_method: str = Field(description="수집된 데이터가 어떤 분석 기법, 소프트웨어 혹은 코딩 접근법을 거쳐 해석되었는지")
    participants: Participants
    keywords_array: List[str] = Field(description="초록 등에서 추출한 영어 원문 키워드 배열")

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 30
