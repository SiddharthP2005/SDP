"""
ResumeTrust Authentication (JWT + PBKDF2)
"""

import jwt
from datetime import datetime, timedelta, timezone
from functools import wraps
from http.server import BaseHTTPRequestHandler
import json
import os

from crypto_utils import hash_password, verify_password
from database import get_connection

JWT_SECRET = os.environ.get("RESUMETRUST_JWT_SECRET", "ResumeTrust-JWT-Secret-Change-In-Production-2026")
JWT_ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 12


def create_token(user_id: int, role: str, email: str) -> str:
    payload = {
        "sub": str(user_id),
        "role": role,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        # PyJWT 2.10+ validates that the JWT subject is a string.
        # Convert it back to an integer for SQLite lookups.
        payload["sub"] = int(payload["sub"])
        return payload
    except jwt.PyJWTError:
        return None


def register_user(email, password, full_name, role, college=None, company=None, student_id=None):
    password_hash, salt = hash_password(password)
    conn = get_connection()
    try:
        cur = conn.execute(
            """INSERT INTO users (email, password_hash, salt, full_name, role, college, company, student_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (email, password_hash, salt, full_name, role, college, company, student_id),
        )
        conn.commit()
        return cur.lastrowid
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def authenticate_user(email, password):
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE lower(email) = lower(?)", (email,)).fetchone()
    conn.close()
    if not row:
        return None
    if verify_password(password, row["password_hash"], row["salt"]):
        return dict(row)
    return None


def get_user_by_id(user_id: int):
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None
