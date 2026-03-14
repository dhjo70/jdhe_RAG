import json
import sqlite3
from typing import Literal, Optional, List, Dict, Any
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

from src.config import GEMINI_API_KEY, MODEL_NAME
from src.database import get_sqlite_conn, get_collection, search_bm25_keywords, search_metadata_filters

client = genai.Client(api_key=GEMINI_API_KEY)

class SqlFilters(BaseModel):
    publication_year: Optional[int] = Field(None, description="출판 연도 조건 (예: 2021). 조건이 명확할 때만 채우세요.")
    methodology_type: Optional[str] = Field(None, description="반드시 다음 중 하나: '질적 연구', '양적 연구', '혼합 연구', '문헌 연구', '기타'")

class SearchQuery(BaseModel):
    sql_filters: SqlFilters = Field(
        description="정확히 일치해야 하는 메타데이터 조건 객체."
    )
    fts_query: str = Field(
        default="",
        description="SQLite FTS5 MATCH 쿼리 문법. 반드시 괄호()를 사용하여 동의어들을 OR 그룹으로 묶고, 서로 구분되는 조건은 AND로 묶어서 연산자 우선순위를 명확히 하세요. (예: '(\"A\" OR \"A 유의어\") AND (\"B\" OR \"B 유의어\")'). 주제가 없으면 빈 문자열 반환."
    )
    semantic_query: str = Field(
        description="문맥적 의미 유사도 검색(Vector DB)을 위한 자연어 질문. 원래의 질문을 검색에 최적화하여 작성."
    )

def analyze_query(user_query: str) -> SearchQuery:
    prompt = f"""
    당신은 JDHE(Journal of Diversity in Higher Education) 논문 DB의 하이브리드 검색 분석기입니다.
    사용자 질문을 분석하여 3가지 검색 엔진(메타데이터 필터, 키워드 검색, 의미론적 검색)에 각각 들어갈 파라미터를 추출하세요.
    - [중요]: fts_query 추출 시, SQLite FTS5 문법을 정확히 준수하세요. 단어들은 반드시 큰따옴표(")로 묶고, 동의어 확장은 괄호()로 묶은 그룹 내부에서 OR 연산하며, 조건들끼리는 AND 연산하세요.
    - [중요]: 검색어의 영어 번역, 약자, 동의어(예: 성적소수자 -> LGBT, Sexual Minority 등)를 파악하여 OR 그룹 안에 넣으세요.
    - 예시: "소수인종이면서 성적소수자인 논문" -> '("소수인종" OR "minority" OR "people of color") AND ("성적소수자" OR "LGBT" OR "Queer" OR "sexual minority")'
    
    질문: "{user_query}"
    """
    
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=SearchQuery,
            temperature=0.0
        )
    )
    return SearchQuery.model_validate_json(response.text)

def execute_vector_search(search_query: str, n_results=20) -> list[str]:
    collection = get_collection()
    for attempt in range(3):
        try:
            results = collection.query(
                query_texts=[search_query],
                n_results=n_results
            )
            break
        except Exception as e:
            if attempt == 2:
                raise RuntimeError("Vector DB가 현재 대용량 데이터 적재로 인해 잠겨있습니다.")
            import time
            time.sleep(1.5)
            
    doc_ids = []
    if results["documents"] and len(results["documents"]) > 0:
        for idx in range(len(results["documents"][0])):
            doc_id = results["metadatas"][0][idx].get("document_id")
            if doc_id and doc_id not in doc_ids:
                doc_ids.append(doc_id)
    return doc_ids

def reciprocal_rank_fusion(ranked_lists: list[list[str]], k=60) -> list[str]:
    scores = {}
    for rank_list in ranked_lists:
        for idx, doc_id in enumerate(rank_list):
            if doc_id not in scores:
                scores[doc_id] = 0.0
            scores[doc_id] += 1.0 / (k + idx + 1)
            
    sorted_docs = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [doc_id for doc_id, score in sorted_docs]

def fetch_document_chunks(document_ids: list[str], max_chunks_per_doc=3) -> list[str]:
    if not document_ids:
        return []
    collection = get_collection()
    results = collection.get(
        where={"document_id": {"$in": document_ids}}
    )
    
    contexts = []
    doc_chunk_count = {}
    for i in range(len(results['ids'])):
        doc_id = results['metadatas'][i]['document_id']
        if doc_id not in doc_chunk_count:
            doc_chunk_count[doc_id] = 0
            
        if doc_chunk_count[doc_id] < max_chunks_per_doc:
            contexts.append(f"[Source: {doc_id}]\n{results['documents'][i]}")
            doc_chunk_count[doc_id] += 1
            
    return contexts

def execute_sql(sql_query: str, params: list = None) -> List[Dict[str, Any]]:
    # A helper for legacy UI tabular display if needed
    conn = get_sqlite_conn()
    cursor = conn.cursor()
    try:
        if params:
            cursor.execute(sql_query, params)
        else:
            cursor.execute(sql_query)
        rows = cursor.fetchall()
        result = [dict(row) for row in rows]
    except Exception as e:
        result = [{"error": str(e)}]
    finally:
        conn.close()
    return result

def retrieve_metadata_for_docs(doc_ids: list[str]) -> list[dict]:
    if not doc_ids: return []
    placeholders = ",".join(["?"] * len(doc_ids))
    sql = f"SELECT * FROM paper_metadata WHERE document_id IN ({placeholders})"
    return execute_sql(sql, doc_ids)

def generate_meta_analysis_response(user_query: str, context: str, total_count: int) -> str:
    prompt = f"""
    당신은 JDHE 저널 논문 메타 분석 전문 AI입니다.
    사용자의 질문에 대해 아래 [통계 및 추출된 논문 데이터]를 바탕으로,
    반드시 다음 형식으로 답변을 작성하세요.

    1. **전체 요약**: "전체 논문 총 {total_count}편 중 조건에 부합하는 논문은 총 O건(O%)입니다. 볼륨 및 이슈별 분포는 다음과 같습니다." 
    2. **볼륨/이슈별 통계**: 각 볼륨과 이슈별 논문 개수를 리스트나 트리 형태로 요약하세요.
    3. **상세 논문 리스트 (Markdown Table)**: 
       반드시 테이블 컬럼을 `| No. | Volume | Issue | 논문 제목 |` 로 구성하고, 첫 번째 `No.` 열에는 1번부터 오름차순으로 순번을 매기세요.

    [사용자 질문]
    {user_query}
    
    [통계 및 추출된 논문 데이터]
    {context}
    """
    
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.1)
    )
    return response.text

def generate_final_response(user_query: str, context: str) -> str:
    prompt = f"""
    당신은 JDHE 저널 논문 분석 전문 AI입니다.
    오직 아래 [제공된 컨텍스트]만을 기반으로 사용자의 질문에 답변하세요.
    응답 마지막에는 반드시 사용된 근거 논문의 리스트(References)를 작성하되, 메타 분석 테이블 포맷과 동일하게 `| No. | Volume | Issue | 논문 제목 |` 구조의 마크다운 테이블(Markdown Table)로 작성해야 합니다. No. 열은 1번부터 오름차순으로 매기세요.
    컨텍스트에 없는 내용을 지어내면(Hallucination) 절대 안 됩니다.
    
    [사용자 질문]
    {user_query}
    
    [제공된 컨텍스트 (DB 검색 결과)]
    {context}
    """
    
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.1)
    )
    return response.text

def generate_conversation_title(user_query: str) -> str:
    prompt = f"""
    다음 사용자의 질문을 분석하여, 대화방의 제목으로 쓸 아주 짧은 키워드 요약(최대 3단어)을 작성하세요.
    예시: 2023년 마이크로어그레션 논문 -> 마이크로어그레션 동향
    
    사용자 질문: "{user_query}"
    """
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.3)
    )
    return response.text.strip().replace('"', '')

def process_query_stream(user_query: str, conversation_id: int, search_mode: str = "meta_analysis"):
    from src.auth import save_message
    
    thought_process = []
    def yield_status(msg):
        thought_process.append(msg)
        return json.dumps({"type": "status", "message": msg}) + "\n"
        
    yield yield_status("🤖 질문의 의도를 분석하고 검색 파라미터를 추출 중입니다...")
    search_params = analyze_query(user_query)
    
    yield yield_status(f"🔍 [1] 메타데이터 필터링 실행 중... (필터: {search_params.sql_filters.model_dump(exclude_none=True)})")
    sql_doc_ids = search_metadata_filters(search_params.sql_filters.model_dump(exclude_none=True))
    
    yield yield_status(f"🔍 [2] BM25 키워드(FTS5) 검색 실행 중... (쿼리: {search_params.fts_query})")
    try:
        bm25_results = search_bm25_keywords(search_params.fts_query)
        bm25_doc_ids = [doc_id for doc_id, score in bm25_results]
    except Exception as e:
        yield yield_status(f"⚠️ BM25 검색 오류 (FTS5 문법 에러 가능성): {e}. 키워드 검색을 건너뜁니다.")
        bm25_doc_ids = []
    
    if search_mode == "deep_insight":
        yield yield_status(f"🔍 [3] 의미론적(Vector DB) 검색 실행 중... (의미 질의: '{search_params.semantic_query}')")
        vector_doc_ids = []
        try:
            vector_doc_ids = execute_vector_search(search_params.semantic_query)
        except RuntimeError as e:
            yield yield_status(f"⏳ {str(e)}")
            
        yield yield_status("🧠 세 가지 검색 결과를 Reciprocal Rank Fusion(RRF) 알고리즘으로 병합 중입니다...")
        
        active_ranks = []
        if bm25_doc_ids: active_ranks.append(bm25_doc_ids)
        if vector_doc_ids: active_ranks.append(vector_doc_ids)
        
        fused_docs = reciprocal_rank_fusion(active_ranks)
        
        if search_params.sql_filters.model_dump(exclude_none=True) and sql_doc_ids:
            fused_docs = [d for d in fused_docs if d in sql_doc_ids]
            
        top_k_docs = fused_docs[:5] # Take absolute top 5
        
        yield yield_status(f"✅ 최고 적합도의 논문 {len(top_k_docs)}건을 추출 완료했습니다. 컨텍스트 구성 중...")
        
        context_chunks = fetch_document_chunks(top_k_docs)
        sql_result = retrieve_metadata_for_docs(top_k_docs)
        
        # Inject metadata into the context chunks so the LLM can build the reference table
        meta_mapped = {row['document_id']: row for row in sql_result}
        enriched_chunks = []
        for chunk in context_chunks:
            doc_id = chunk.split("[Source: ")[1].split("]")[0]
            if doc_id in meta_mapped:
                m = meta_mapped[doc_id]
                meta_str = f"[Metadata] Title: {m.get('title')} | Volume: {m.get('volume')} | Issue: {m.get('issue')}\n"
                enriched_chunks.append(meta_str + chunk)
            else:
                enriched_chunks.append(chunk)
                
        context_str = "\n---\n".join(enriched_chunks)
        
        yield yield_status("💡 하이브리드 심층 검색 결과를 기반으로 최종 답변을 구성 중입니다...")
        final_answer = generate_final_response(user_query, context_str)
        
    else:
        # meta_analysis mode
        yield yield_status("📊 조건에 맞는 논문 전수 조사를 위한 교집합 분석 중입니다...")
        
        has_sql = bool(search_params.sql_filters.model_dump(exclude_none=True))
        has_bm25 = bool(search_params.fts_query.strip())
        
        all_matched_docs = []
        if has_sql and has_bm25:
            all_matched_docs = [d for d in sql_doc_ids if d in bm25_doc_ids]
        elif has_sql:
            all_matched_docs = sql_doc_ids
        elif has_bm25:
            all_matched_docs = bm25_doc_ids
        else:
            all_matched_docs = sql_doc_ids
            
        yield yield_status(f"✅ 조건에 맞는 논문 총 {len(all_matched_docs)}건을 확보했습니다. 통계 집계 중...")
        
        sql_result = retrieve_metadata_for_docs(all_matched_docs)
        
        vol_issue_counts = {}
        for row in sql_result:
            vol = row.get("volume", "Unknown")
            issue = row.get("issue", "Unknown")
            key = f"Vol {vol} / Issue {issue}"
            vol_issue_counts[key] = vol_issue_counts.get(key, 0) + 1
            
        context_str = f"Total Matches: {len(all_matched_docs)}\nCounts by Volume/Issue:\n"
        for k, v in sorted(vol_issue_counts.items()):
            context_str += f"- {k}: {v} articles\n"
            
        context_str += "\nDetailed List:\n"
        for row in sql_result:
            context_str += f"- Title: {row.get('title')} | Vol: {row.get('volume')} Issue: {row.get('issue')}\n"
        
        yield yield_status("💡 조사된 통계 및 논문 목록을 기반으로 요약 마크다운 테이블을 생성 중입니다...")
        total_count_res = execute_sql("SELECT COUNT(*) as count FROM paper_metadata")
        total_count = total_count_res[0].get('count', 0) if total_count_res else 0
        final_answer = generate_meta_analysis_response(user_query, context_str, total_count)
        context_chunks = []
    
    sql_data_json = json.dumps(sql_result, ensure_ascii=False) if sql_result else None
    thought_process_json = json.dumps(thought_process, ensure_ascii=False) if thought_process else None
    
    save_message(conversation_id, "assistant", final_answer, search_mode, sql_data_json, thought_process_json)
    
    yield json.dumps({
        "type": "result",
        "data": {
            "intent": search_params.model_dump(),
            "sql_result": sql_result,
            "vector_result": context_chunks if search_mode == "deep_insight" else [],
            "final_answer": final_answer
        }
    }) + "\n"
