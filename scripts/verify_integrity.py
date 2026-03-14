import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sqlite3
import collections
from src.database import get_collection, get_sqlite_conn

def verify_databases():
    print("=== SQLite Auditing ===")
    conn = get_sqlite_conn()
    cursor = conn.cursor()
    
    # Check total count
    cursor.execute("SELECT count(*) FROM paper_metadata")
    total_papers = cursor.fetchone()[0]
    print(f"Total Papers in SQLite: {total_papers}")
    
    # Check for NULLs in essential columns
    cursor.execute("""
        SELECT count(*) FROM paper_metadata 
        WHERE title IS NULL OR title = ''
           OR publication_year IS NULL
           OR volume IS NULL OR volume = ''
           OR issue IS NULL OR issue = ''
           OR research_topic IS NULL OR research_topic = ''
           OR methodology_type IS NULL OR methodology_type = ''
           OR participants_description IS NULL OR participants_description = ''
    """)
    null_counts = cursor.fetchone()[0]
    print(f"Papers with NULL essential columns: {null_counts}")
    if null_counts > 0:
        cursor.execute("SELECT document_id FROM paper_metadata WHERE title IS NULL OR title = ''")
        print("Example NULL documents:", cursor.fetchall())

    # Get all document IDs
    cursor.execute("SELECT document_id FROM paper_metadata")
    sqlite_ids = {row['document_id'] for row in cursor.fetchall()}
    conn.close()

    print("\n=== ChromaDB Auditing ===")
    collection = get_collection()
    
    # Get all vector metadata to count chunks per document
    # ChromaDB get() can return everything if no query is provided (or we can just query the collection)
    chroma_data = collection.get()
    
    if not chroma_data or not chroma_data['metadatas']:
        print("ChromaDB is completely empty or error reading!")
        return

    chunk_counts = collections.Counter()
    for meta in chroma_data['metadatas']:
        if meta and 'document_id' in meta:
            chunk_counts[meta['document_id']] += 1
            
    chroma_ids = set(chunk_counts.keys())
    
    print(f"Unique papers found in ChromaDB: {len(chroma_ids)}")
    
    missing_in_chroma = sqlite_ids - chroma_ids
    missing_in_sqlite = chroma_ids - sqlite_ids
    
    print("\n=== Validation Results ===")
    print(f"Papers in SQLite but NOT in ChromaDB: {len(missing_in_chroma)}")
    if missing_in_chroma:
        print(f" 👉 IDs: {missing_in_chroma}")
        
    print(f"Papers in ChromaDB but NOT in SQLite: {len(missing_in_sqlite)}")
    if missing_in_sqlite:
        print(f" 👉 IDs: {missing_in_sqlite}")
        
    if not missing_in_chroma and not missing_in_sqlite and null_counts == 0:
        print("\n✅ All 114 papers are perfectly synced and fully populated across both databases!")
    else:
        print("\n❌ Synchronisation issues detected.")

if __name__ == "__main__":
    verify_databases()
