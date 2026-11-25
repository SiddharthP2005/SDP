"""
ResumeTrust Cryptographic Utilities
Implements the exact CNS concepts described:
- AES-256-GCM for resume encryption/decryption
- SHA-256 for integrity fingerprint
- PBKDF2-HMAC-SHA256 for password hashing
- HMAC-SHA256 for audit log integrity
"""

import os
import sqlite3
import hashlib
import hmac
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

# Master encryption key for resumes (in production use KMS / env var)
# 32 bytes = 256-bit key
RESUME_MASTER_KEY = os.environ.get(
    "RESUME_MASTER_KEY",
    "ResumeTrust-Demo-Master-Key-32B!!"  # exactly 32 bytes for demo
).encode("utf-8")[:32]

AUDIT_HMAC_KEY = os.environ.get(
    "AUDIT_HMAC_KEY",
    "ResumeTrust-Audit-HMAC-Secret-Key"
).encode("utf-8")


def sha256_hash(data: bytes) -> str:
    """Step 2 – SHA-256 fingerprint of the original resume."""
    return hashlib.sha256(data).hexdigest()


def encrypt_resume(plaintext: bytes, associated_data: bytes = b"ResumeTrust") -> dict:
    """
    Step 3 – AES-256-GCM encryption.
    Returns ciphertext, nonce, and authentication tag (all base64).
    """
    if len(RESUME_MASTER_KEY) != 32:
        raise ValueError("Master key must be 32 bytes")

    aesgcm = AESGCM(RESUME_MASTER_KEY)
    nonce = os.urandom(12)  # 96-bit nonce recommended for GCM
    ciphertext = aesgcm.encrypt(nonce, plaintext, associated_data)

    # AESGCM returns ciphertext || tag (last 16 bytes are the tag)
    tag = ciphertext[-16:]
    ct = ciphertext[:-16]

    return {
        "ciphertext": base64.b64encode(ct).decode("utf-8"),
        "nonce": base64.b64encode(nonce).decode("utf-8"),
        "tag": base64.b64encode(tag).decode("utf-8"),
        "aad": associated_data.decode("utf-8") if associated_data else None,
    }


def decrypt_resume(
    ciphertext_b64: str,
    nonce_b64: str,
    tag_b64: str,
    associated_data: bytes = b"ResumeTrust",
) -> bytes:
    """
    Decrypt + authenticate with AES-256-GCM.
    Raises InvalidTag if authentication fails (tampering detected).
    """
    aesgcm = AESGCM(RESUME_MASTER_KEY)
    nonce = base64.b64decode(nonce_b64)
    ct = base64.b64decode(ciphertext_b64)
    tag = base64.b64decode(tag_b64)

    # Reconstruct ciphertext || tag expected by AESGCM
    ciphertext_with_tag = ct + tag
    plaintext = aesgcm.decrypt(nonce, ciphertext_with_tag, associated_data)
    return plaintext


def verify_integrity(original_hash: str, decrypted_bytes: bytes) -> bool:
    """Compare SHA-256 of decrypted content with stored original hash."""
    return hmac.compare_digest(original_hash.lower(), sha256_hash(decrypted_bytes))


def hash_password(password: str, salt: bytes = None) -> tuple[str, str]:
    """
    PBKDF2-HMAC-SHA256 password hashing (as listed in CNS topics).
    Returns (hash_hex, salt_hex)
    """
    if salt is None:
        salt = os.urandom(16)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100_000,
        backend=default_backend(),
    )
    key = kdf.derive(password.encode("utf-8"))
    return key.hex(), salt.hex()


def verify_password(password: str, stored_hash: str, salt_hex: str) -> bool:
    salt = bytes.fromhex(salt_hex)
    new_hash, _ = hash_password(password, salt)
    return hmac.compare_digest(new_hash, stored_hash)


def hmac_sign(data: str) -> str:
    """HMAC-SHA256 for protecting audit-log integrity."""
    return hmac.new(AUDIT_HMAC_KEY, data.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_hmac(data: str, signature: str) -> bool:
    expected = hmac_sign(data)
    return hmac.compare_digest(expected, signature)

# Public-key envelope encryption used by the live student upload workflow.
# The browser encrypts each resume with a one-time AES-256-GCM key, then
# wraps that key with the Placement Cell RSA public key (RSA-OAEP/SHA-256).
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization

KEY_DIR = os.path.join(os.path.dirname(__file__), "keys")
PRIVATE_KEY_PATH = os.path.join(KEY_DIR, "placement_private.pem")
PUBLIC_KEY_PATH = os.path.join(KEY_DIR, "placement_public.pem")


def ensure_placement_keypair():
    os.makedirs(KEY_DIR, exist_ok=True)
    if not os.path.exists(PRIVATE_KEY_PATH):
        # Never silently rotate a key if RSA-wrapped resumes already exist.
        db_path = os.path.join(os.path.dirname(__file__), "resumetrust.db")
        if os.path.exists(db_path):
            try:
                conn = sqlite3.connect(db_path)
                tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
                if "resumes" in tables:
                    cols = {r[1] for r in conn.execute("PRAGMA table_info(resumes)").fetchall()}
                    if "wrapped_key" in cols and conn.execute("SELECT 1 FROM resumes WHERE wrapped_key IS NOT NULL LIMIT 1").fetchone():
                        conn.close()
                        raise RuntimeError("Placement private key is missing, but encrypted resumes exist. Restore keys/placement_private.pem from backup; do not generate a replacement key.")
                conn.close()
            except RuntimeError:
                raise
            except Exception:
                pass
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
        private_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        public_bytes = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        with open(PRIVATE_KEY_PATH, "wb") as f:
            f.write(private_bytes)
        with open(PUBLIC_KEY_PATH, "wb") as f:
            f.write(public_bytes)
    elif not os.path.exists(PUBLIC_KEY_PATH):
        with open(PRIVATE_KEY_PATH, "rb") as f:
            private_key = serialization.load_pem_private_key(f.read(), password=None)
        with open(PUBLIC_KEY_PATH, "wb") as f:
            f.write(private_key.public_key().public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            ))
    with open(PUBLIC_KEY_PATH, "rb") as f:
        return f.read().decode("ascii")


def decrypt_student_envelope(ciphertext_b64, nonce_b64, tag_b64, wrapped_key_b64, aad=b"ResumeTrust-Student-Upload"):
    """Placement-side RSA-OAEP unwrap + AES-256-GCM decrypt."""
    import base64
    ensure_placement_keypair()
    with open(PRIVATE_KEY_PATH, "rb") as f:
        private_key = serialization.load_pem_private_key(f.read(), password=None)
    aes_key = private_key.decrypt(
        base64.b64decode(wrapped_key_b64),
        padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
    )
    nonce = base64.b64decode(nonce_b64)
    ciphertext = base64.b64decode(ciphertext_b64)
    tag = base64.b64decode(tag_b64)
    return AESGCM(aes_key).decrypt(nonce, ciphertext + tag, aad)
