import json
import sqlite3
from typing import Literal, Optional, List, Dict, Any
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

from src.config import GEMINI_API_KEY, MODEL_NAME
from src.database import get_sqlite_conn, get_collection

client = genai.Client(api_key=GEMINI_API_KEY)

class QueryIntent(BaseModel):
    intent_type: Literal["quantitative", "qualitative", "hybrid"] = Field(
        description="quantitative: 통계/수치/메타데이터 분석, qualitative: 내용상 의미 검색, hybrid: 메타데이터 필터링 + 내용 검색"
    )
    sql_query: Optional[str] = Field(
        description="quantitative나 hybrid일 경우 SQLite metadata_table(paper_metadata)에 대해 실행할 SQL 쿼리. 필드: document_id, title, publication_year, volume, issue, research_topic, methodology_type, methodology_details, participants_description, participants_target_groups(JSON), participants_sample_size, keywords(JSON). json 필드에는 json_extract 등을 사용. 데이터 조회가 목적이면 document_id 등 필요 컬럼 반환."
    )
    search_query: Optional[str] = Field(
        description="qualitative나 hybrid일 경우 Vector DB에서 검색할 자연어 쿼리 의미."
    )

def get_distinct_methodologies() -> str:
    conn = get_sqlite_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT DISTINCT methodology_type FROM paper_metadata WHERE methodology_type IS NOT NULL")
        rows = cursor.fetchall()
        valid_types = [row[0] for row in rows]
        return ", ".join([f"'{t}'" for t in valid_types if t.strip()])
    except:
        return "'질적 연구', '양적 연구', '혼합방법 연구'"
    finally:
        conn.close()

def route_query(user_query: str) -> QueryIntent:
    valid_methodologies = get_distinct_methodologies()
    
    prompt = f"""
    당신은 JDHE(Journal of Diversity in Higher Education) 논문 DB의 핵심 라우터입니다.
    사용자 쿼리가 다음 중 어떤 의도인지 분석하고 JSON 스키마에 맞게 쿼리 계획을 세우세요.
    1. quantitative (정량적): 연도별 추세, 표본 크기 평균, 연구 유형(methodology_type) 비율 등 메타데이터만으로 계산되는 쿼리.
    2. qualitative (정성적): "특권 취약성이란?", "마이크로어그레션의 사례는?" 등 논문 본문 내용에 대한 의미 검색.
    3. hybrid (복합적): 특정 메타데이터 조건 + 본문 내용 검색 (예: 2023년 논문 중에서 흑인 여성을 대상으로 한 임포스터 증후군 관련 사례는?)

    [SQL 테이블 스키마 참고 (SQLite)]
    Table: paper_metadata
    - document_id (TEXT, PK)
    - title (TEXT)
    - publication_year (INTEGER)
    - volume (TEXT)
    - issue (TEXT)
    - research_topic (TEXT)
    - theoretical_framework (TEXT)
    - methodology_type (TEXT, Enum values: {valid_methodologies})
    - methodology_details (TEXT)
    - data_collection_method (TEXT)
    - data_analysis_method (TEXT)
    - participants_description (TEXT)
    - participants_target_groups (JSON)
    - participants_sample_size (INTEGER)
    - keywords (JSON)

    * Data Matching Rule: methodology_type 조건 검색 시 반드시 위 Enum 값 중 하나와 일치(LIKE '%...%')하도록 쿼리를 작성하세요.

    질문: "{user_query}"
    """
    
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=QueryIntent,
            temperature=0.0
        )
    )
    return QueryIntent.model_validate_json(response.text)

def execute_sql(sql_query: str) -> List[Dict[str, Any]]:
    conn = get_sqlite_conn()
    cursor = conn.cursor()
    try:
        cursor.execute(sql_query)
        rows = cursor.fetchall()
        result = [dict(row) for row in rows]
    except Exception as e:
        print(f"SQL Execution Error: {e}")
        result = [{"error": str(e)}]
    finally:
        conn.close()
    return result

def execute_vector_search(search_query: str, filter_doc_ids: Optional[List[str]] = None, n_results=5) -> List[str]:
    collection = get_collection()
    where_clause = None
    if filter_doc_ids:
        if len(filter_doc_ids) == 1:
            where_clause = {"document_id": filter_doc_ids[0]}
        else:
            where_clause = {"document_id": {"$in": filter_doc_ids}}
            
    for attempt in range(3):
        try:
            results = collection.query(
                query_texts=[search_query],
                n_results=n_results,
                where=where_clause
            )
            break
        except Exception as e:
            if attempt == 2:
                raise RuntimeError("Vector DB가 현재 대용량 데이터 적재로 인해 잠겨있습니다.")
            import time
            time.sleep(1.5)
            
    contexts = []
    if results["documents"] and len(results["documents"]) > 0:
        for idx, doc in enumerate(results["documents"][0]):
            doc_id = results["metadatas"][0][idx].get("document_id", "Unknown")
            contexts.append(f"[Source: {doc_id}]\n{doc}")
            
    return contexts

def generate_final_response(user_query: str, context: str) -> str:
    prompt = f"""
    당신은 JDHE 저널 논문 분석 전문 AI입니다.
    오직 아래 [제공된 컨텍스트]만을 기반으로 사용자의 질문에 답변하세요.
    응답 아래에는 반드시 사용된 근거 논문의 리스트(References)를 작성하세요.
    컨텍스트에 없는 내용을 지어내면(Hallucination) 절대 안 됩니다. 모르는 것은 모른다고 하세요.
    
    [사용자 질문]
    {user_query}
    
    [제공된 컨텍스트 (DB 검색/통계 결과)]
    {context}
    """
    
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.1
        )
    )
    return response.text

def generate_conversation_title(user_query: str) -> str:
    prompt = f"""
    다음 사용자의 질문을 분석하여, 대화방의 제목으로 쓸 아주 짧은 키워드 요약(최대 3단어)을 작성하세요.
    예시: 2023년 마이크로어그레션 논문 -> 마이크로어그레션 동향
    예시: 특권 취약성이란? -> 특권 취약성 개념
    
    사용자 질문: "{user_query}"
    """
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.3)
    )
    return response.text.strip().replace('"', '')

def process_query_stream(user_query: str, conversation_id: int):
    from src.auth import save_message
    
    thought_process = []
    def yield_status(msg):
        thought_process.append(msg)
        return json.dumps({"type": "status", "message": msg}) + "\n"
        
    yield yield_status("🤖 질문의 의도를 분석하고 라우팅 계획을 수립 중입니다...")
    
    intent = route_query(user_query)
    intent_kr = "정량적(통계)" if intent.intent_type == "quantitative" else "정성적(의미)" if intent.intent_type == "qualitative" else "복합적(통계+의미)"
    yield yield_status(f"🔍 의도 분석 완료: **{intent_kr} 검색**으로 처리합니다.")
    
    sql_result = None
    vector_result = None
    context_str = f"Query Intent: {intent.intent_type}\n\n"
    
    is_truncated = False
    if intent.intent_type in ["quantitative", "hybrid"] and intent.sql_query:
        yield yield_status(f"📊 메타데이터(SQLite) 검색을 위한 SQL 쿼리를 실행합니다:\n`{intent.sql_query}`")
        sql_result = execute_sql(intent.sql_query)
        yield yield_status(f"✅ SQL 검색 완료 (총 {len(sql_result)}개의 통계/데이터 확인)")
        
        context_sql_result = sql_result
        if isinstance(sql_result, list) and len(sql_result) > 100:
            context_sql_result = sql_result[:100]
            is_truncated = True
            yield yield_status("⚠️ API 비용 절약을 위해 AI 분석용 데이터는 100건으로 제한합니다.")
            
        context_str += f"SQL Query Executed: {intent.sql_query}\nSQL Result (Limited to 100 items): {json.dumps(context_sql_result, ensure_ascii=False)}\n\n"
        
    doc_id_filters = None
    if intent.intent_type == "hybrid" and sql_result:
        # Try to extract document_ids to filter vector search
        doc_id_filters = [row["document_id"] for row in sql_result if "document_id" in row]
        if not doc_id_filters: # If no explicit IDs, proceed without filter or perhaps it's empty
            doc_id_filters = ["NON_EXISTENT_ID"] if "error" not in str(sql_result) else None
        else:
            yield yield_status(f"🎯 Hybrid 필터링: SQL 조건에 맞는 {len(doc_id_filters)}개의 논문 ID를 벡터 DB 검색 조건으로 설정했습니다.")

    if intent.intent_type in ["qualitative", "hybrid"] and intent.search_query:
        yield yield_status(f"🧠 의미 검색(ChromaDB)을 시작합니다. 검색 키워드: *'{intent.search_query}'*")
        try:
            vector_result = execute_vector_search(intent.search_query, filter_doc_ids=doc_id_filters)
            yield yield_status(f"✅ Vector DB 검색 완료 (가장 유사도 높은 논문 조각 추출 완료)")
            context_str += f"Vector Search Query: {intent.search_query}\nVector Result Chunks:\n" + "\n---\n".join(vector_result)
        except RuntimeError as e:
            yield yield_status(f"⏳ {str(e)} 잠시 후 다시 질문해주세요.")
            vector_result = []
        
    yield yield_status("💡 검색된 모든 데이터(SQL 결과 및 의미 추출 결과)를 조합하여 최종 답변을 문서화하고 있습니다...")
    final_answer = generate_final_response(user_query, context_str)
    
    if is_truncated:
        final_answer += "\n\n*(⚠️ API 비용 절감을 위해 AI 텍스트 분석에는 최대 100개의 논문만 반영되었습니다. 전체 통계/데이터는 하단 표를 참고해주세요.)*"
    
    
    # Save assistant message to history
    sql_data_json = json.dumps(sql_result, ensure_ascii=False) if sql_result else None
    thought_process_json = json.dumps(thought_process, ensure_ascii=False) if thought_process else None
    save_message(conversation_id, "assistant", final_answer, intent.intent_type, sql_data_json, thought_process_json)
    
    yield json.dumps({
        "type": "result",
        "data": {
            "intent": intent.model_dump(),
            "sql_result": sql_result,
            "vector_result": vector_result,
            "final_answer": final_answer
        }
    }) + "\n"
