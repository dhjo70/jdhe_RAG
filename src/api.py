import os
from fastapi import FastAPI, BackgroundTasks, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import Optional, List
from src.auth import (
    User, get_current_user, get_password_hash, get_user_by_username,
    create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES, get_auth_conn,
    create_conversation, get_conversations, get_messages, save_message
)
from datetime import timedelta

import os
import sqlite3
from src.pdf_utils import extract_text_from_pdf_file
from src.llm_client import extract_metadata_from_paper
from src.database import insert_paper_metadata, insert_paper_vectors
from src.query_router import process_query_stream

app = FastAPI(title="JDHE Hybrid RAG API")

class QueryRequest(BaseModel):
    query: str
    conversation_id: int

class QueryResponse(BaseModel):
    intent: dict
    sql_result: Optional[list] | Optional[dict]
    vector_result: Optional[list]
    final_answer: str

from fastapi.responses import StreamingResponse

class UserCreate(BaseModel):
    username: str
    password: str

@app.post("/register")
def register(user: UserCreate):
    existing = get_user_by_username(user.username)
    if existing:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    hashed_password = get_password_hash(user.password)
    conn = get_auth_conn()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO users (username, hashed_password) VALUES (?, ?)", (user.username, hashed_password))
    conn.commit()
    conn.close()
    return {"message": "User created successfully"}

@app.post("/token")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    from src.auth import verify_password
    user = get_user_by_username(form_data.username)
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"]}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

class ConversationCreate(BaseModel):
    title: str

@app.post("/conversations")
def create_new_conversation(conv_data: ConversationCreate, current_user: User = Depends(get_current_user)):
    conv_id = create_conversation(current_user.id, conv_data.title)
    return {"id": conv_id, "title": conv_data.title}

@app.get("/conversations")
def list_conversations(current_user: User = Depends(get_current_user)):
    return get_conversations(current_user.id)

@app.get("/conversations/{conversation_id}/messages")
def list_messages(conversation_id: int, current_user: User = Depends(get_current_user)):
    return get_messages(conversation_id, current_user.id)

@app.delete("/conversations/{conversation_id}")
def delete_conv(conversation_id: int, current_user: User = Depends(get_current_user)):
    from src.auth import delete_conversation
    success = delete_conversation(conversation_id, current_user.id)
    if not success:
        raise HTTPException(status_code=403, detail="Not authorized to delete this conversation")
    return {"message": "Deleted"}

@app.post("/query")
def query_endpoint(req: QueryRequest, current_user: User = Depends(get_current_user)):
    try:
        from src.query_router import process_query_stream
        from src.auth import save_message, get_conversation, update_conversation_title
        # Save the user query to DB before processing
        save_message(req.conversation_id, "user", req.query)
        
        # Rename new conversation automatically based on first query
        conv = get_conversation(req.conversation_id)
        if conv and conv.get("title") == "New Conversation":
            from src.query_router import generate_conversation_title
            try:
                new_title = generate_conversation_title(req.query)
                update_conversation_title(req.conversation_id, new_title)
            except Exception:
                pass
                
        # Pass conversation_id to process_query_stream so it can save the assistant's final answer
        return StreamingResponse(process_query_stream(req.query, req.conversation_id), media_type="application/x-ndjson")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def get_existing_ids():
    try:
        conn = sqlite3.connect('data/metadata.db')
        cursor = conn.cursor()
        cursor.execute("SELECT document_id FROM paper_metadata")
        existing_ids = set(row[0] for row in cursor.fetchall())
        conn.close()
        return existing_ids
    except Exception:
        return set()

def background_ingest():
    """Background task to ingest local PDFs from the 'papers' directory into DBs."""
    print("Starting local background ingestion pipeline...")
    base_dir = "papers"
    existing_ids = get_existing_ids()
    
    if not os.path.exists(base_dir):
        print(f"Directory {base_dir} not found. Please run the download script first.")
        return
        
    for vol_name in sorted(os.listdir(base_dir)):
        vol_path = os.path.join(base_dir, vol_name)
        if not os.path.isdir(vol_path): continue
        
        for issue_name in sorted(os.listdir(vol_path)):
            issue_path = os.path.join(vol_path, issue_name)
            if not os.path.isdir(issue_path): continue
            
            for pdf_name in os.listdir(issue_path):
                if not pdf_name.endswith('.pdf'): continue
                
                document_id = pdf_name.replace(".pdf", "").strip()
                
                if document_id in existing_ids:
                    continue
                
                pdf_path = os.path.join(issue_path, pdf_name)
                print(f"Processing {document_id} from {vol_name} / {issue_name} (Local)...")
                
                paper_text = extract_text_from_pdf_file(pdf_path)
                if not paper_text.strip():
                    continue
                    
                metadata = extract_metadata_from_paper(paper_text, document_id, vol_name, issue_name)
                if metadata:
                    insert_paper_metadata(metadata)
                    insert_paper_vectors(document_id, paper_text)
                    print(f"Ingested {document_id} successfully.")
                    existing_ids.add(document_id)
                else:
                    print(f"Failed to extract metadata for {document_id}")
    print("Local ingestion pipeline completed!")

@app.post("/ingest")
async def start_ingest(background_tasks: BackgroundTasks):
    background_tasks.add_task(background_ingest)
    return {"message": "Ingestion started in the background. Check logs for progress."}
