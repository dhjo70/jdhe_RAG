import os
import sqlite3
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
import sys

# Python 3.12+ passlib bcrypt compat bug workarounds
pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")

SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "fallback-secret-key-jdhe-rag-2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days session

AUTH_DB_PATH = "data/auth.db"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class User(BaseModel):
    username: str
    id: int

class Conversation(BaseModel):
    id: int
    user_id: int
    title: str
    created_at: str

def get_auth_conn():
    os.makedirs(os.path.dirname(AUTH_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(AUTH_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_auth_db():
    conn = get_auth_conn()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            role TEXT NOT NULL, -- 'user' or 'assistant'
            content TEXT NOT NULL,
            intent_type TEXT,
            sql_data JSON,
            thought_process JSON,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_id) REFERENCES conversations (id)
        )
    """)
    conn.commit()
    conn.close()

# Initialize on load
init_auth_db()

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def get_user_by_username(username: str):
    conn = get_auth_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
        
    user = get_user_by_username(token_data.username)
    if user is None:
        raise credentials_exception
    return User(username=user["username"], id=user["id"])

# --- Conversation & Message DB Helpers ---

def create_conversation(user_id: int, title: str):
    conn = get_auth_conn()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO conversations (user_id, title) VALUES (?, ?)", (user_id, title))
    conn.commit()
    inserted_id = cursor.lastrowid
    conn.close()
    return inserted_id

def get_conversation(conversation_id: int):
    conn = get_auth_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def update_conversation_title(conversation_id: int, title: str):
    conn = get_auth_conn()
    cursor = conn.cursor()
    cursor.execute("UPDATE conversations SET title = ? WHERE id = ?", (title, conversation_id))
    conn.commit()
    conn.close()

def delete_conversation(conversation_id: int, user_id: int):
    conn = get_auth_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM conversations WHERE id=? AND user_id=?", (conversation_id, user_id))
    if not cursor.fetchone():
        conn.close()
        return False
    cursor.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
    cursor.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
    conn.commit()
    conn.close()
    return True

def get_conversations(user_id: int):
    conn = get_auth_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, created_at FROM conversations WHERE user_id = ? ORDER BY id DESC", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_messages(conversation_id: int, user_id: int):
    # Verify ownership
    conn = get_auth_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM conversations WHERE id = ?", (conversation_id,))
    row = cursor.fetchone()
    if not row or row["user_id"] != user_id:
        conn.close()
        return []
        
    cursor.execute("SELECT role, content, intent_type, sql_data, thought_process, created_at FROM messages WHERE conversation_id = ? ORDER BY id ASC", (conversation_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def save_message(conversation_id: int, role: str, content: str, intent_type: str = None, sql_data: str = None, thought_process: str = None):
    conn = get_auth_conn()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO messages (conversation_id, role, content, intent_type, sql_data, thought_process)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (conversation_id, role, content, intent_type, sql_data, thought_process))
    conn.commit()
    conn.close()
