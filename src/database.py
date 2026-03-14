import os
import sqlite3
import json
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

from src.config import SQLITE_DB_PATH, CHROMA_DB_PATH, GEMINI_API_KEY, PaperMetadata

# Use Gemini Embedding function for ChromaDB
# If not explicitly supported by chromadb cleanly, we can use default chromadb embedder 
# or implement a custom one. For simplicity and 100% semantic matching with Gemini, 
# let's use the default all-MiniLM-L6-v2 model built-in to ChromaDB, or Google Generative AI embeddings.
try:
    google_ef = embedding_functions.GoogleGenerativeAiEmbeddingFunction(api_key=GEMINI_API_KEY)
except Exception:
    google_ef = embedding_functions.DefaultEmbeddingFunction()

def get_sqlite_conn():
    os.makedirs(os.path.dirname(SQLITE_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_sqlite_db():
    conn = get_sqlite_conn()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS paper_metadata (
            document_id TEXT PRIMARY KEY,
            title TEXT,
            publication_year INTEGER,
            volume TEXT,
            issue TEXT,
            research_topic TEXT,
            theoretical_framework TEXT,
            methodology_type TEXT,
            methodology_details TEXT,
            data_collection_method TEXT,
            data_analysis_method TEXT,
            participants_description TEXT,
            participants_target_groups JSON,
            participants_sample_size INTEGER,
            keywords JSON,
            ingest_status TEXT DEFAULT 'PROCESSING'
        )
    """)
    
    # Create FTS5 Virtual Table for BM25 Keyword Search
    cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS paper_fts USING fts5(
            document_id UNINDEXED, 
            title, 
            research_topic, 
            keywords
        )
    """)
    
    # Triggers to keep FTS in sync with the main table
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS paper_metadata_after_insert AFTER INSERT ON paper_metadata 
        BEGIN
            INSERT INTO paper_fts(rowid, document_id, title, research_topic, keywords) 
            VALUES (new.rowid, new.document_id, new.title, new.research_topic, new.keywords);
        END;
    """)
    
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS paper_metadata_after_delete AFTER DELETE ON paper_metadata 
        BEGIN
            INSERT INTO paper_fts(paper_fts, rowid, document_id, title, research_topic, keywords) 
            VALUES ('delete', old.rowid, old.document_id, old.title, old.research_topic, old.keywords);
        END;
    """)
    
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS paper_metadata_after_update AFTER UPDATE ON paper_metadata 
        BEGIN
            INSERT INTO paper_fts(paper_fts, rowid, document_id, title, research_topic, keywords) 
            VALUES ('delete', old.rowid, old.document_id, old.title, old.research_topic, old.keywords);
            
            INSERT INTO paper_fts(rowid, document_id, title, research_topic, keywords) 
            VALUES (new.rowid, new.document_id, new.title, new.research_topic, new.keywords);
        END;
    """)
    
    conn.commit()
    conn.close()

def search_bm25_keywords(keywords: list[str], top_k: int = 20) -> list[tuple[str, float]]:
    if not keywords:
        return []
        
    conn = get_sqlite_conn()
    cursor = conn.cursor()
    
    # FTS5 uses string queries, e.g. "keyword1" OR "keyword2"
    # We construct a simple OR query to maximize recall
    escaped_keywords = [f'"{kw.replace("\"", "")}"' for kw in keywords]
    fts_query = " OR ".join(escaped_keywords)
    
    # FTS5 rank is heavily negative for better matches. We return the absolute value or reciprocal.
    cursor.execute("""
        SELECT document_id, rank
        FROM paper_fts 
        WHERE paper_fts MATCH ?
        ORDER BY rank
        LIMIT ?
    """, (fts_query, top_k))
    
    results = [(row['document_id'], abs(row['rank'])) for row in cursor.fetchall()]
    conn.close()
    return results

def search_metadata_filters(filters: dict) -> list[str]:
    if not filters:
        # If no filters exist, we can technically return all document_ids, but that's inefficient.
        # Usually, if there are no filters, the caller will not rely on this pool.
        # Here we will just return everything so the intersection works mathematically later.
        conn = get_sqlite_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT document_id FROM paper_metadata WHERE ingest_status = 'COMPLETED'")
        rows = cursor.fetchall()
        conn.close()
        return [r['document_id'] for r in rows]

    conn = get_sqlite_conn()
    cursor = conn.cursor()
    
    query = "SELECT document_id FROM paper_metadata WHERE ingest_status = 'COMPLETED'"
    params = []
    
    for key, value in filters.items():
        if isinstance(value, list) and value:
            # e.g., year in [2021, 2022]
            placeholders = ', '.join(['?'] * len(value))
            query += f" AND {key} IN ({placeholders})"
            params.extend(value)
        elif value is not None and value != "":
            # e.g., methodology_type = '질적 연구'
            query += f" AND {key} = ?"
            params.append(value)
            
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [r['document_id'] for r in rows]

def check_paper_exists(document_id: str) -> bool:
    # 1. Check SQLite for COMPLETED status
    conn = get_sqlite_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM paper_metadata WHERE document_id = ? AND ingest_status = 'COMPLETED'", (document_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row is None:
        return False
        
    # 2. Check ChromaDB
    try:
        collection = get_collection()
        results = collection.get(
            where={"document_id": document_id},
            limit=1
        )
        if not results or not results.get("ids"):
            return False
    except Exception:
        return False
        
    return True

def insert_paper_metadata(metadata: PaperMetadata, status: str = 'PROCESSING'):
    conn = get_sqlite_conn()
    cursor = conn.cursor()
    
    target_groups_json = json.dumps(metadata.participants.target_groups_array, ensure_ascii=False)
    keywords_json = json.dumps(metadata.keywords_array, ensure_ascii=False)
    
    cursor.execute("""
        INSERT OR REPLACE INTO paper_metadata (
            document_id, title, publication_year, volume, issue,
            research_topic, theoretical_framework, methodology_type, methodology_details,
            data_collection_method, data_analysis_method,
            participants_description, participants_target_groups,
            participants_sample_size, keywords, ingest_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        metadata.document_id,
        metadata.title,
        metadata.publication_year,
        metadata.volume,
        metadata.issue,
        metadata.research_topic,
        metadata.theoretical_framework,
        metadata.methodology.type,
        metadata.methodology.details,
        metadata.data_collection_method,
        metadata.data_analysis_method,
        metadata.participants.description,
        target_groups_json,
        metadata.participants.sample_size_integer,
        keywords_json,
        status
    ))
    conn.commit()
    conn.close()

def mark_paper_completed(document_id: str):
    conn = get_sqlite_conn()
    cursor = conn.cursor()
    cursor.execute("UPDATE paper_metadata SET ingest_status = 'COMPLETED' WHERE document_id = ?", (document_id,))
    conn.commit()
    conn.close()

def get_chroma_client():
    os.makedirs(os.path.dirname(CHROMA_DB_PATH), exist_ok=True)
    client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    return client

def get_collection():
    client = get_chroma_client()
    return client.get_or_create_collection(
        name="jdhe_papers",
        embedding_function=google_ef
    )

def chunk_text(text: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> list[str]:
    """
    Very basic semantic chunking based on word count with overlap.
    """
    words = text.split()
    chunks = []
    if not words:
        return chunks
        
    i = 0
    while i < len(words):
        chunk_words = words[i:i + chunk_size]
        chunks.append(" ".join(chunk_words))
        i += (chunk_size - chunk_overlap)
    return chunks

def insert_paper_vectors(document_id: str, paper_text: str):
    """
    Chunks paper text and inserts into ChromaDB.
    """
    collection = get_collection()
    chunks = chunk_text(paper_text, chunk_size=800, chunk_overlap=150)
    
    documents = []
    metadatas = []
    ids = []
    
    for idx, chunk in enumerate(chunks):
        documents.append(chunk)
        metadatas.append({"document_id": document_id})
        ids.append(f"{document_id}_chunk_{idx}")
        
    if documents:
        # We can just upsert
        collection.upsert(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )

# Initialize DBs on module load or manually
init_sqlite_db()
