import sqlite3
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.database import get_collection, get_sqlite_conn

def clean_string(s):
    # Remove all punctuation and spaces for fuzzy matching
    return ''.join(c for c in s if c.isalnum()).lower()

def run_alignment():
    conn = get_sqlite_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT document_id FROM paper_metadata")
    sqlite_ids = [r[0] for r in cursor.fetchall()]
    
    collection = get_collection()
    chroma_data = collection.get()
    
    chroma_ids = set()
    for meta in chroma_data['metadatas']:
        if meta and 'document_id' in meta:
            chroma_ids.add(meta['document_id'])
            
    mismatched_sql = [s for s in sqlite_ids if s not in chroma_ids]
    mismatched_chroma = [c for c in chroma_ids if c not in sqlite_ids]
    
    # Map by cleaned string
    sql_map = {clean_string(s): s for s in mismatched_sql}
    updates = 0
    for c_id in mismatched_chroma:
        cleaned_c = clean_string(c_id)
        if cleaned_c in sql_map:
            old_sql_id = sql_map[cleaned_c]
            # Perform update
            cursor.execute("UPDATE paper_metadata SET document_id = ? WHERE document_id = ?", (c_id, old_sql_id))
            updates += 1
            print(f"✅ Aligned: '{old_sql_id}' -> '{c_id}'")
            
    conn.commit()
    conn.close()
    print(f"Total aligned: {updates}")

if __name__ == '__main__':
    run_alignment()
