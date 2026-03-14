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
            keywords JSON
        )
    """)
    conn.commit()
    conn.close()

def check_paper_exists(document_id: str) -> bool:
    # 1. Check SQLite
    conn = get_sqlite_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM paper_metadata WHERE document_id = ?", (document_id,))
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

def insert_paper_metadata(metadata: PaperMetadata):
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
            participants_sample_size, keywords
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        keywords_json
    ))
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
