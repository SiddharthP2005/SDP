"""
ResumeTrust SQLite Database Layer
"""

import sqlite3
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "resumetrust.db"


def get_connection():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    # Users (Student / Placement Cell / Company HR)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('student', 'placement', 'hr')),
            college TEXT,
            company TEXT,
            student_id TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Placement Drives
    cur.execute("""
        CREATE TABLE IF NOT EXISTS placement_drives (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            company_name TEXT NOT NULL,
            description TEXT,
            eligibility TEXT,
            deadline TEXT,
            created_by INTEGER,
            status TEXT DEFAULT 'open',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    """)

    # Student participation in drives
    cur.execute("""
        CREATE TABLE IF NOT EXISTS drive_registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            drive_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            registered_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(drive_id, student_id),
            FOREIGN KEY (drive_id) REFERENCES placement_drives(id),
            FOREIGN KEY (student_id) REFERENCES users(id)
        )
    """)

    # Encrypted Resumes
    cur.execute("""
        CREATE TABLE IF NOT EXISTS resumes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            original_filename TEXT NOT NULL,
            sha256_hash TEXT NOT NULL,
            ciphertext TEXT NOT NULL,
            nonce TEXT NOT NULL,
            auth_tag TEXT NOT NULL,
            aad TEXT,
            wrapped_key TEXT,
            encryption_method TEXT DEFAULT 'AES-256-GCM',
            uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP,
            decrypted_by_placement INTEGER DEFAULT 0,
            integrity_verified INTEGER DEFAULT 0,
            decrypted_at TEXT,
            verified_by_placement INTEGER DEFAULT 0,
            verification_notes TEXT,
            forwarded_to_hr INTEGER DEFAULT 0,
            forwarded_at TEXT,
            FOREIGN KEY (student_id) REFERENCES users(id)
        )
    """)

    # Academic records (authorised by Placement Cell for verification)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS academic_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            tenth_percentage REAL,
            twelfth_percentage REAL,
            degree_cgpa REAL,
            degree_name TEXT,
            branch TEXT,
            year_of_passing INTEGER,
            FOREIGN KEY (student_id) REFERENCES users(id)
        )
    """)

    # Resume Access Requests (from Company HR)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS access_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            resume_id INTEGER NOT NULL,
            hr_id INTEGER NOT NULL,
            drive_id INTEGER,
            status TEXT DEFAULT 'pending'
                CHECK(status IN ('pending', 'student_approved', 'placement_approved',
                                 'granted', 'rejected', 'revoked', 'expired')),
            student_consent INTEGER DEFAULT 0,
            placement_approval INTEGER DEFAULT 0,
            requested_at TEXT DEFAULT CURRENT_TIMESTAMP,
            expires_at TEXT,
            notes TEXT,
            FOREIGN KEY (resume_id) REFERENCES resumes(id),
            FOREIGN KEY (hr_id) REFERENCES users(id),
            FOREIGN KEY (drive_id) REFERENCES placement_drives(id)
        )
    """)

    # Audit Log (HMAC protected)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor_id INTEGER,
            action TEXT NOT NULL,
            resource_type TEXT,
            resource_id INTEGER,
            details TEXT,
            hmac_signature TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Lightweight forward-only migrations for databases created by earlier demos.
    existing = {row[1] for row in cur.execute("PRAGMA table_info(resumes)").fetchall()}
    migrations = {
        "wrapped_key": "ALTER TABLE resumes ADD COLUMN wrapped_key TEXT",
        "encryption_method": "ALTER TABLE resumes ADD COLUMN encryption_method TEXT DEFAULT 'AES-256-GCM'",
        "decrypted_by_placement": "ALTER TABLE resumes ADD COLUMN decrypted_by_placement INTEGER DEFAULT 0",
        "integrity_verified": "ALTER TABLE resumes ADD COLUMN integrity_verified INTEGER DEFAULT 0",
        "decrypted_at": "ALTER TABLE resumes ADD COLUMN decrypted_at TEXT",
        "forwarded_to_hr": "ALTER TABLE resumes ADD COLUMN forwarded_to_hr INTEGER DEFAULT 0",
        "forwarded_at": "ALTER TABLE resumes ADD COLUMN forwarded_at TEXT",
    }
    for column, sql in migrations.items():
        if column not in existing:
            cur.execute(sql)
    # Label records from older versions accurately; they used server-side demo encryption.
    cur.execute("UPDATE resumes SET encryption_method = 'Legacy demo AES-256-GCM' WHERE wrapped_key IS NULL AND (encryption_method IS NULL OR encryption_method = 'AES-256-GCM')")

    conn.commit()
    conn.close()
    print("Database initialized successfully.")


def add_audit_log(actor_id, action, resource_type=None, resource_id=None, details=""):
    from crypto_utils import hmac_sign
    payload = f"{actor_id}|{action}|{resource_type}|{resource_id}|{details}|{datetime.now(timezone.utc).isoformat()}"
    signature = hmac_sign(payload)

    conn = get_connection()
    conn.execute(
        """INSERT INTO audit_logs (actor_id, action, resource_type, resource_id, details, hmac_signature)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (actor_id, action, resource_type, resource_id, details, signature),
    )
    conn.commit()
    conn.close()
