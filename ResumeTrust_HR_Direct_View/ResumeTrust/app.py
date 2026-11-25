#!/usr/bin/env python3
"""
ResumeTrust – Secure Resume Verification & Placement Platform
Main application server (pure Python HTTP + JSON API)
"""

import json
import os
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from datetime import datetime, timedelta, timezone
import traceback

from database import init_db, get_connection, add_audit_log
from auth import (
    create_token, decode_token, authenticate_user,
    register_user, get_user_by_id
)
from crypto_utils import (
    encrypt_resume, decrypt_resume, sha256_hash,
    verify_integrity, hmac_sign, ensure_placement_keypair, decrypt_student_envelope
)

STATIC_DIR = Path(__file__).parent / "static"
UPLOAD_DIR = Path(__file__).parent / "uploads"
DEMO_DIR = Path(__file__).parent / "demo_resumes"
PORT = int(os.environ.get("PORT", "8081"))

UPLOAD_DIR.mkdir(exist_ok=True)


class ResumeTrustHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0]}")

    def _set_headers(self, status=200, content_type="application/json"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def _json_response(self, data, status=200):
        self._set_headers(status)
        self.wfile.write(json.dumps(data, default=str).encode("utf-8"))

    def _error(self, message, status=400):
        self._json_response({"success": False, "error": message}, status)

    def _get_json_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ValueError("Request body must contain valid JSON")
        if not isinstance(value, dict):
            raise ValueError("Request body must be a JSON object")
        return value

    def _get_token_user(self):
        # Header names can vary in case across platforms
        auth = self.headers.get("Authorization") or self.headers.get("authorization") or ""
        print(f"  [AUTH] Authorization header = {auth[:50] + '...' if len(auth) > 50 else auth!r}")
        if not auth.startswith("Bearer ") and not auth.startswith("bearer "):
            print("  [AUTH] No Bearer token found")
            return None
        token = auth.split(" ", 1)[1].strip()
        payload = decode_token(token)
        print(f"  [AUTH] Token payload = {payload}")
        if not payload:
            print("  [AUTH] Token decode FAILED")
            return None
        user = get_user_by_id(payload["sub"])
        print(f"  [AUTH] User found = {user['email'] if user else None}")
        return user

    def do_OPTIONS(self):
        self._set_headers(204)

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)

        # Serve static files / frontend
        if path == "/" or path == "/index.html":
            self._serve_file(STATIC_DIR / "index.html", "text/html")
            return
        if path.startswith("/static/"):
            file_path = STATIC_DIR / path[len("/static/"):]
            if file_path.exists():
                ctype = "text/css" if path.endswith(".css") else "application/javascript" if path.endswith(".js") else "text/plain"
                self._serve_file(file_path, ctype)
                return
            self._error("Not found", 404)
            return

        # API routes
        if path == "/api/health":
            self._json_response({"status": "ok", "app": "ResumeTrust", "version": "2.0"})
            return
        if path == "/api/crypto/public-key":
            try:
                self._json_response({"success": True, "public_key": ensure_placement_keypair()})
            except RuntimeError as exc:
                self._error(str(exc), 503)
            return

        user = self._get_token_user()
        if not user and path.startswith("/api/"):
            self._error("Unauthorized – please login", 401)
            return

        if path == "/api/me":
            self._json_response({
                "success": True,
                "user": {
                    "id": user["id"],
                    "email": user["email"],
                    "full_name": user["full_name"],
                    "role": user["role"],
                    "college": user["college"],
                    "company": user["company"],
                    "student_id": user["student_id"],
                }
            })
            return

        if path == "/api/drives":
            self._list_drives(user)
            return

        if path == "/api/resumes":
            self._list_resumes(user)
            return

        if path == "/api/access-requests":
            self._list_access_requests(user)
            return

        if path.startswith("/api/resumes/") and path.endswith("/download"):
            resume_id = int(path.split("/")[3])
            self._download_resume(user, resume_id, inline=False)
            return

        if path.startswith("/api/resumes/") and path.endswith("/view"):
            resume_id = int(path.split("/")[3])
            self._download_resume(user, resume_id, inline=True)
            return

        if path == "/api/academic-records":
            self._list_academic_records(user)
            return

        if path == "/api/audit-logs":
            if user["role"] != "placement":
                self._error("Only Placement Cell can view audit logs", 403)
                return
            self._list_audit_logs()
            return

        self._error("Not found", 404)

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path

        if path == "/api/login":
            self._login()
            return

        if path == "/api/register":
            self._register()
            return

        user = self._get_token_user()
        if not user:
            self._error("Unauthorized – please login", 401)
            return

        if path == "/api/resumes/upload":
            self._upload_resume(user)
            return

        if path == "/api/access-requests":
            self._create_access_request(user)
            return

        if path.startswith("/api/access-requests/") and path.endswith("/student-consent"):
            req_id = int(path.split("/")[3])
            self._student_consent(user, req_id)
            return

        if path.startswith("/api/access-requests/") and path.endswith("/placement-approve"):
            req_id = int(path.split("/")[3])
            self._placement_approve(user, req_id)
            return

        if path.startswith("/api/access-requests/") and path.endswith("/reject"):
            req_id = int(path.split("/")[3])
            self._reject_request(user, req_id)
            return

        if path.startswith("/api/resumes/") and path.endswith("/verify"):
            resume_id = int(path.split("/")[3])
            self._verify_resume(user, resume_id)
            return

        if path.startswith("/api/resumes/") and path.endswith("/forward"):
            resume_id = int(path.split("/")[3])
            self._forward_resume(user, resume_id)
            return

        if path == "/api/drives":
            self._create_drive(user)
            return

        self._error("Not found", 404)

    def _serve_file(self, path, content_type):
        try:
            with open(path, "rb") as f:
                data = f.read()
            self._set_headers(200, content_type)
            self.wfile.write(data)
        except Exception:
            self._error("File not found", 404)

    # ---------- Auth ----------
    def _login(self):
        try:
            body = self._get_json_body()
        except ValueError as exc:
            self._error(str(exc), 400)
            return
        email = str(body.get("email", "")).strip().lower()
        password = body.get("password", "")
        if not email or not isinstance(password, str) or not password:
            self._error("Email and password are required", 400)
            return
        user = authenticate_user(email, password)
        if not user:
            self._error("Invalid email or password", 401)
            return
        token = create_token(user["id"], user["role"], user["email"])
        print(f"  [LOGIN] User={email} id={user['id']} token={token[:40]}...")
        add_audit_log(user["id"], "LOGIN", details=f"User logged in: {email}")
        self._json_response({
            "success": True,
            "token": token,
            "user": {
                "id": user["id"],
                "email": user["email"],
                "full_name": user["full_name"],
                "role": user["role"],
                "college": user["college"],
                "company": user["company"],
            }
        })

    def _register(self):
        body = self._get_json_body()
        try:
            uid = register_user(
                email=body["email"],
                password=body["password"],
                full_name=body["full_name"],
                role=body.get("role", "student"),
                college=body.get("college"),
                company=body.get("company"),
                student_id=body.get("student_id"),
            )
            self._json_response({"success": True, "user_id": uid})
        except Exception as e:
            self._error(str(e), 400)

    # ---------- Drives ----------
    def _list_drives(self, user):
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM placement_drives ORDER BY created_at DESC"
        ).fetchall()
        drives = [dict(r) for r in rows]
        conn.close()
        self._json_response({"success": True, "drives": drives})

    def _create_drive(self, user):
        if user["role"] != "placement":
            self._error("Only Placement Cell can create drives", 403)
            return
        body = self._get_json_body()
        conn = get_connection()
        cur = conn.execute(
            """INSERT INTO placement_drives
               (title, company_name, description, eligibility, deadline, created_by)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (body["title"], body["company_name"], body.get("description"),
             body.get("eligibility"), body.get("deadline"), user["id"]),
        )
        conn.commit()
        drive_id = cur.lastrowid
        conn.close()
        add_audit_log(user["id"], "CREATE_DRIVE", "drive", drive_id, body["title"])
        self._json_response({"success": True, "drive_id": drive_id})

    # ---------- Resumes ----------
    def _list_resumes(self, user):
        conn = get_connection()
        base = """SELECT r.id, r.original_filename, r.sha256_hash, r.uploaded_at,
                         r.verified_by_placement, r.verification_notes,
                         r.decrypted_by_placement, r.integrity_verified, r.decrypted_at,
                         r.forwarded_to_hr, r.forwarded_at, r.encryption_method,
                         u.full_name, u.email, u.student_id, u.college
                  FROM resumes r JOIN users u ON r.student_id = u.id"""
        if user["role"] == "student":
            rows = conn.execute(base + " WHERE r.student_id = ? ORDER BY r.uploaded_at DESC", (user["id"],)).fetchall()
        elif user["role"] == "hr":
            # HR only receives resumes explicitly forwarded by the Placement Cell.
            rows = conn.execute(base + " WHERE r.forwarded_to_hr = 1 ORDER BY r.forwarded_at DESC").fetchall()
        else:
            rows = conn.execute(base + " ORDER BY r.uploaded_at DESC").fetchall()
        resumes = [dict(r) for r in rows]
        conn.close()
        self._json_response({"success": True, "resumes": resumes})

    def _upload_resume(self, user):
        if user["role"] != "student":
            self._error("Only students can upload resumes", 403)
            return
        body = self._get_json_body()
        filename = os.path.basename(str(body.get("filename", "resume.pdf")))
        b64_content = body.get("content_base64")
        if not b64_content:
            self._error("Missing encrypted resume content")
            return
        import base64
        try:
            ciphertext_and_tag = base64.b64decode(b64_content, validate=True)
            nonce = base64.b64decode(body.get("nonce", ""), validate=True)
            wrapped_key = body.get("wrapped_key", "")
            file_hash = str(body.get("sha256", ""))
            if (len(nonce) != 12 or len(ciphertext_and_tag) < 16 or
                    len(ciphertext_and_tag) > 10 * 1024 * 1024 + 16 or not wrapped_key or
                    len(file_hash) != 64 or any(c not in "0123456789abcdefABCDEF" for c in file_hash)):
                raise ValueError("Incomplete or oversized encrypted package")
            ciphertext, tag = ciphertext_and_tag[:-16], ciphertext_and_tag[-16:]
            # AES-GCM AAD is fixed and shared with the browser implementation.
            aad = "ResumeTrust-Student-Upload"
        except Exception:
            self._error("Invalid encrypted upload package. Please select the PDF and retry.", 400)
            return

        conn = get_connection()
        # Keep prior submissions as history; the latest upload is the active one.
        cur = conn.execute(
            """INSERT INTO resumes
               (student_id, original_filename, sha256_hash, ciphertext, nonce, auth_tag,
                aad, wrapped_key, encryption_method)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user["id"], filename, file_hash, base64.b64encode(ciphertext).decode("ascii"),
             base64.b64encode(nonce).decode("ascii"), base64.b64encode(tag).decode("ascii"),
             aad, wrapped_key, "RSA-OAEP-3072 + AES-256-GCM"),
        )
        resume_id = cur.lastrowid
        conn.commit()
        conn.close()
        add_audit_log(user["id"], "STUDENT_ENCRYPTED_UPLOAD", "resume", resume_id,
                      "Browser AES-256-GCM encryption; AES key wrapped with Placement RSA-OAEP public key")
        self._json_response({
            "success": True, "resume_id": resume_id, "sha256": file_hash,
            "message": "Encrypted in the student's browser and securely submitted to Placement Cell",
            "encryption": "AES-256-GCM", "key_wrapping": "RSA-OAEP-SHA256"
        })

    def _verify_resume(self, user, resume_id):
        if user["role"] != "placement":
            self._error("Only Placement Cell can decrypt and verify resumes", 403)
            return
        body = self._get_json_body()
        notes = body.get("notes", "Decrypted by Placement Cell; SHA-256 integrity matched")
        conn = get_connection()
        row = conn.execute("SELECT * FROM resumes WHERE id = ?", (resume_id,)).fetchone()
        if not row:
            conn.close()
            self._error("Resume not found", 404)
            return
        resume = dict(row)
        try:
            if resume.get("wrapped_key"):
                plaintext = decrypt_student_envelope(
                    resume["ciphertext"], resume["nonce"], resume["auth_tag"],
                    resume["wrapped_key"], (resume["aad"] or "ResumeTrust-Student-Upload").encode("utf-8")
                )
            else:
                plaintext = decrypt_resume(resume["ciphertext"], resume["nonce"], resume["auth_tag"],
                                           (resume["aad"] or "ResumeTrust").encode("utf-8"))
            if not plaintext.startswith(b"%PDF-"):
                raise ValueError("Decrypted upload is not a valid PDF file")
            if not verify_integrity(resume["sha256_hash"], plaintext):
                raise ValueError("SHA-256 mismatch: decrypted file failed integrity verification")
        except Exception as exc:
            conn.close()
            add_audit_log(user["id"], "DECRYPT_OR_INTEGRITY_FAILED", "resume", resume_id, str(exc))
            self._error("Decryption or integrity verification failed. The resume must not be forwarded.", 422)
            return

        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """UPDATE resumes SET decrypted_by_placement = 1, integrity_verified = 1,
               decrypted_at = ?, verification_notes = ? WHERE id = ?""",
            (now, notes, resume_id),
        )
        conn.commit()
        conn.close()
        add_audit_log(user["id"], "PLACEMENT_DECRYPTED", "resume", resume_id,
                      "RSA-OAEP key unwrap + AES-256-GCM decryption completed")
        add_audit_log(user["id"], "SHA256_INTEGRITY_VERIFIED", "resume", resume_id,
                      "Original SHA-256 fingerprint matches decrypted bytes")
        self._json_response({
            "success": True, "resume_id": resume_id, "decrypted": True,
            "integrity_verified": True, "sha256": resume["sha256_hash"],
            "bytes_verified": len(plaintext), "message": "Placement Cell decrypted the resume and SHA-256 integrity matched."
        })

    def _forward_resume(self, user, resume_id):
        if user["role"] != "placement":
            self._error("Only Placement Cell can forward resumes to Company HR", 403)
            return
        conn = get_connection()
        row = conn.execute("SELECT integrity_verified, verified_by_placement FROM resumes WHERE id = ?", (resume_id,)).fetchone()
        if not row:
            conn.close()
            self._error("Resume not found", 404)
            return
        body = self._get_json_body()
        if not row["integrity_verified"] or not body.get("review_confirmed"):
            conn.close()
            self._error("Decrypt the resume and confirm that you reviewed its details against official academic records before forwarding", 400)
            return
        now = datetime.now(timezone.utc).isoformat()
        conn.execute("UPDATE resumes SET verified_by_placement = 1, forwarded_to_hr = 1, forwarded_at = ?, verification_notes = COALESCE(verification_notes, 'Placement review confirmed') WHERE id = ?", (now, resume_id))
        conn.commit()
        conn.close()
        add_audit_log(user["id"], "FORWARDED_TO_COMPANY_HR", "resume", resume_id,
                      "Placement officer confirmed manual review against official academic records; resume released to Company HR queue")
        self._json_response({"success": True, "message": "Verified resume forwarded to Company HR successfully."})

    def _download_resume(self, user, resume_id, inline=False):
        """
        Securely decrypt and serve a resume after re-checking SHA-256.
        HR access is allowed only after Placement Cell has verified and forwarded it.
        inline=True is used by the authenticated in-app PDF viewer.
        """
        conn = get_connection()
        resume = conn.execute(
            "SELECT * FROM resumes WHERE id = ?", (resume_id,)
        ).fetchone()
        if not resume:
            conn.close()
            self._error("Resume not found", 404)
            return

        resume = dict(resume)
        allowed = False

        # The student already has the original local file. Decryption of the
        # server-stored envelope is reserved for Placement Cell / approved HR.
        if user["role"] == "placement":
            allowed = bool(resume.get("integrity_verified"))
        elif user["role"] == "hr":
            # Forwarding by Placement Cell is the explicit release/access checkpoint.
            # No separate HR request, student consent, or second approval is required.
            allowed = bool(resume.get("integrity_verified") and
                           resume.get("verified_by_placement") and
                           resume.get("forwarded_to_hr"))

        if not allowed:
            conn.close()
            self._error("You can view or download this resume only after Placement Cell verifies and forwards it", 403)
            return

        try:
            if resume.get("wrapped_key"):
                plaintext = decrypt_student_envelope(
                    resume["ciphertext"], resume["nonce"], resume["auth_tag"],
                    resume["wrapped_key"], (resume["aad"] or "ResumeTrust-Student-Upload").encode("utf-8")
                )
            else:
                plaintext = decrypt_resume(
                    resume["ciphertext"], resume["nonce"], resume["auth_tag"],
                    (resume["aad"] or "ResumeTrust").encode("utf-8"),
                )
            if not verify_integrity(resume["sha256_hash"], plaintext):
                conn.close()
                add_audit_log(user["id"], "INTEGRITY_FAIL", "resume", resume_id)
                self._error("Integrity check failed – resume may have been tampered with", 500)
                return

            action = "VIEW_RESUME" if inline else "DOWNLOAD_RESUME"
            add_audit_log(user["id"], action, "resume", resume_id,
                          "SHA-256 match confirmed; " + ("opened in in-app PDF viewer" if inline else "downloaded"))
            conn.close()

            safe_filename = os.path.basename(resume["original_filename"]).replace('"', '')
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Disposition",
                             f'{"inline" if inline else "attachment"}; filename="{safe_filename}"')
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(plaintext)
        except Exception as e:
            conn.close()
            add_audit_log(user["id"], "DECRYPT_FAIL", "resume", resume_id, str(e))
            self._error(f"Decryption failed: {str(e)}", 500)

    # ---------- Access Requests ----------
    def _list_access_requests(self, user):
        conn = get_connection()
        if user["role"] == "hr":
            rows = conn.execute(
                """SELECT ar.*, r.original_filename, u.full_name as student_name
                   FROM access_requests ar
                   JOIN resumes r ON ar.resume_id = r.id
                   JOIN users u ON r.student_id = u.id
                   WHERE ar.hr_id = ?
                   ORDER BY ar.requested_at DESC""",
                (user["id"],),
            ).fetchall()
        elif user["role"] == "student":
            rows = conn.execute(
                """SELECT ar.*, r.original_filename, hu.full_name as hr_name, hu.company
                   FROM access_requests ar
                   JOIN resumes r ON ar.resume_id = r.id
                   JOIN users hu ON ar.hr_id = hu.id
                   WHERE r.student_id = ?
                   ORDER BY ar.requested_at DESC""",
                (user["id"],),
            ).fetchall()
        else:  # placement
            rows = conn.execute(
                """SELECT ar.*, r.original_filename, u.full_name as student_name,
                          hu.full_name as hr_name, hu.company
                   FROM access_requests ar
                   JOIN resumes r ON ar.resume_id = r.id
                   JOIN users u ON r.student_id = u.id
                   JOIN users hu ON ar.hr_id = hu.id
                   ORDER BY ar.requested_at DESC"""
            ).fetchall()
        requests = [dict(r) for r in rows]
        conn.close()
        self._json_response({"success": True, "requests": requests})

    def _create_access_request(self, user):
        if user["role"] != "hr":
            self._error("Only Company HR can request resume access", 403)
            return
        body = self._get_json_body()
        resume_id = body.get("resume_id")
        drive_id = body.get("drive_id")
        notes = body.get("notes", "")

        conn = get_connection()
        # Check resume exists and is verified
        resume = conn.execute(
            "SELECT * FROM resumes WHERE id = ?", (resume_id,)
        ).fetchone()
        if not resume:
            conn.close()
            self._error("Resume not found", 404)
            return
        if not resume["verified_by_placement"] or not resume["forwarded_to_hr"]:
            conn.close()
            self._error("Resume must be verified and forwarded by Placement Cell before HR can request access", 400)
            return

        expires = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        cur = conn.execute(
            """INSERT INTO access_requests
               (resume_id, hr_id, drive_id, status, notes, expires_at)
               VALUES (?, ?, ?, 'pending', ?, ?)""",
            (resume_id, user["id"], drive_id, notes, expires),
        )
        req_id = cur.lastrowid
        conn.commit()
        conn.close()
        add_audit_log(user["id"], "REQUEST_ACCESS", "access_request", req_id,
                      f"resume_id={resume_id}")
        self._json_response({
            "success": True,
            "request_id": req_id,
            "message": "Access request submitted. Waiting for student consent and Placement Cell approval."
        })

    def _student_consent(self, user, req_id):
        if user["role"] != "student":
            self._error("Only the student can give consent", 403)
            return
        conn = get_connection()
        req = conn.execute(
            """SELECT ar.*, r.student_id FROM access_requests ar
               JOIN resumes r ON ar.resume_id = r.id WHERE ar.id = ?""",
            (req_id,),
        ).fetchone()
        if not req or req["student_id"] != user["id"]:
            conn.close()
            self._error("Request not found or not yours", 404)
            return

        new_status = "student_approved"
        # If placement already approved, move to granted
        if req["placement_approval"]:
            new_status = "granted"

        conn.execute(
            "UPDATE access_requests SET student_consent = 1, status = ? WHERE id = ?",
            (new_status, req_id),
        )
        conn.commit()
        conn.close()
        add_audit_log(user["id"], "STUDENT_CONSENT", "access_request", req_id)
        self._json_response({"success": True, "status": new_status})

    def _placement_approve(self, user, req_id):
        if user["role"] != "placement":
            self._error("Only Placement Cell can approve", 403)
            return
        conn = get_connection()
        req = conn.execute("SELECT * FROM access_requests WHERE id = ?", (req_id,)).fetchone()
        if not req:
            conn.close()
            self._error("Request not found", 404)
            return

        new_status = "placement_approved"
        if req["student_consent"]:
            new_status = "granted"

        conn.execute(
            "UPDATE access_requests SET placement_approval = 1, status = ? WHERE id = ?",
            (new_status, req_id),
        )
        conn.commit()
        conn.close()
        add_audit_log(user["id"], "PLACEMENT_APPROVE", "access_request", req_id)
        self._json_response({"success": True, "status": new_status})

    def _reject_request(self, user, req_id):
        if user["role"] not in ("student", "placement"):
            self._error("Not allowed", 403)
            return
        conn = get_connection()
        conn.execute(
            "UPDATE access_requests SET status = 'rejected' WHERE id = ?",
            (req_id,),
        )
        conn.commit()
        conn.close()
        add_audit_log(user["id"], "REJECT_REQUEST", "access_request", req_id)
        self._json_response({"success": True, "status": "rejected"})

    # ---------- Academic & Audit ----------
    def _list_academic_records(self, user):
        conn = get_connection()
        if user["role"] == "student":
            rows = conn.execute(
                "SELECT * FROM academic_records WHERE student_id = ?", (user["id"],)
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT ar.*, u.full_name, u.email, u.student_id
                   FROM academic_records ar JOIN users u ON ar.student_id = u.id"""
            ).fetchall()
        records = [dict(r) for r in rows]
        conn.close()
        self._json_response({"success": True, "records": records})

    def _list_audit_logs(self):
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT 100"
        ).fetchall()
        logs = [dict(r) for r in rows]
        conn.close()
        self._json_response({"success": True, "logs": logs})


def main():
    # Always apply safe schema migrations and ensure the Placement Cell keypair exists.
    if not (Path(__file__).parent / "resumetrust.db").exists():
        print("Database not found. Running demo seed...")
        from seed import seed
        seed()
    else:
        init_db()
    ensure_placement_keypair()

    server = HTTPServer(("0.0.0.0", PORT), ResumeTrustHandler)
    print("=" * 60)
    print("  ResumeTrust – Secure Resume Verification Platform")
    print("=" * 60)
    print(f"  Server running at http://localhost:{PORT}")
    print(f"  Open the URL in your browser to use the application.")
    print("=" * 60)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.server_close()


if __name__ == "__main__":
    main()
