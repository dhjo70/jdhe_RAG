import os
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import Optional, List, Literal

# Load environment variables
load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY가 설정되지 않았습니다. .env 파일에 추가해주세요.")


MODEL_NAME = 'gemini-2.5-flash-lite'

# Database Settings
SQLITE_DB_PATH = 'data/metadata.db'
CHROMA_DB_PATH = 'data/chroma_db'

# Extraction Schema (FR1)
class Methodology(BaseModel):
    type: Literal["질적 연구", "양적 연구", "혼합 연구", "문헌 연구", "기타"] = Field(
        description="연구 접근 유형. 반드시 주어진 5가지 중 하나만 선택하세요."
    )
    details: str = Field(description="구체적 연구 방법 명칭 (예: 설문조사, 현상학 등). 없으면 '미상'")

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
    theoretical_framework: str = Field(description="연구의 이론적 배경 명칭 (문장이 아닌 핵심 전문용어/학자 이름만 간결하게). 명시되지 않았다면 '미상'")
    methodology: Methodology
    data_collection_method: str = Field(description="데이터 수집 절차 (문장이 아닌 간결한 명사형 중심). 없으면 '미상'")
    data_analysis_method: str = Field(description="분석 기법 및 소프트웨어 (문장이 아닌 간결한 명사형 중심). 없으면 '미상'")
    participants: Participants
    keywords_array: List[str] = Field(description="초록 등에서 추출한 영어 원문 키워드 배열")

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 30
