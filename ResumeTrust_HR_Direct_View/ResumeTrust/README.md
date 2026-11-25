# ResumeTrust — Secure Resume Verification & Placement Platform

## Windows quick start

1. Install Python 3.10+ and enable **Add Python to PATH**.
2. Extract the project ZIP.
3. Double-click `start_windows.bat`.
4. Open http://localhost:8081.

The launcher creates a virtual environment and installs dependencies. It creates demo data only when no database exists; an existing `resumetrust.db` is preserved.

To start manually from this folder:

```bat
py -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python -c "from database import init_db; init_db()"
python app.py
```

For a first-time demo database only, run `python seed.py` before starting the server. **Warning:** `seed.py` resets the demo database and deletes existing records. Do not run it if you need to preserve your data.

## Demo login credentials

| Role | Email | Password |
|---|---|---|
| Placement Cell | `placement@college.edu` | `Placement@123` |
| Company HR | `hr@techcorp.com` | `HR@Tech123` |
| Student — Arjun | `arjun.sharma@college.edu` | `Student@123` |
| Student — Priya | `priya.patel@college.edu` | `Student@123` |
| Student — Rahul | `rahul.mehta@college.edu` | `Student@123` |

## Health check

Visit http://localhost:8081/api/health. A running server responds with JSON containing `"status": "ok"`.

## Security workflow and CNS concepts

- AES-256-GCM encrypts resume files at rest.
- SHA-256 fingerprints support integrity checking after decryption.
- PBKDF2-HMAC-SHA256 hashes account passwords.
- HMAC-SHA256 protects audit-log entries.
- JWT authenticates API requests; role-based checks separate Student, Placement and HR actions.

This is an educational demonstration. Before production use, replace demo secrets with environment-managed secrets, deploy behind HTTPS, add rate limiting, and use a managed key service.

## Troubleshooting

- If port 8081 is occupied, close the other process or run `set PORT=8082` before `python app.py` (then open port 8082).
- If login succeeds but the dashboard returns to login, clear the site's local storage or sign out and sign in again. This build fixes the PyJWT 2.10+ `sub` claim compatibility issue.
- If a dependency fails to install, run `python -m pip install --upgrade pip` and then `python -m pip install -r requirements.txt`.

## Live student → Placement Cell → Company HR workflow (v2)

1. Sign in as a **Student** and open **My Resume**.
2. Choose a PDF (up to 10 MB) and select **Encrypt & Submit to Placement Cell**.
   - Encryption happens in the student's browser using a fresh AES-256-GCM key and nonce.
   - The browser calculates a SHA-256 fingerprint of the original PDF.
   - The one-time AES key is wrapped with the Placement Cell RSA-OAEP/SHA-256 public key.
   - Only ciphertext, nonce, authentication tag, wrapped key and fingerprint are stored by the server. The Placement Cell performs verification decryption. Once Placement Cell verifies the resume and forwards it, HR can immediately view the PDF in the in-app viewer or download it.
3. Sign in as **Placement Cell** and open **Placement Cell Verification Desk**.
4. Select **Decrypt & Verify**. The server uses the Placement Cell private key to unwrap the AES key, decrypts the PDF with AES-256-GCM, and checks that the decrypted bytes have the same SHA-256 fingerprint. A failed decrypt or hash comparison blocks forwarding.
5. After the check passes, select **Forward to Company HR**. The resume now appears in the Company HR dashboard; unforwarded resumes are hidden from HR.
6. Sign in as **Company HR**. Every resume forwarded by Placement Cell appears in **Student Resumes** with **View Document** and **Download PDF** actions. No separate HR access request, student consent, or second Placement approval is required. Every view/download re-decrypts the stored ciphertext, re-checks SHA-256, and records an audit event.
7. Placement Cell **Audit Log** records browser-encrypted upload, placement decryption, SHA-256 verification, forwarding, PDF-view and download events.

### Cryptographic design note

This is an educational demonstration. The RSA private key is stored on the application server so the Placement Cell role can perform the controlled decryption step. **Back up `keys/placement_private.pem` securely and never delete or regenerate it after encrypted uploads exist**; the application refuses to silently rotate a missing key when RSA-encrypted resumes are present. For a real deployment, keep that private key in a KMS/HSM, deploy only over HTTPS, apply strict file-size and malware scanning controls, and avoid sharing the server filesystem or key with HR accounts. HR can view or download the resume only after Placement Cell has verified and forwarded it; forwarding releases the resume to the HR queue.
