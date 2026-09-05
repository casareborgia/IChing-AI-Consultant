# -*- coding: utf-8 -*-
"""
주역 상담 앱 - 민감 데이터 암호화 모듈 (AES-256-GCM)
- 내담자의 내밀한 심리 성찰(Aha moment)과 전념 행동 다짐(Action pledge)을 암호화하여 저장/처리합니다.
- NIST 권고 표준인 AES-256-GCM(Authenticated Encryption with Associated Data)을 사용합니다.
- 매 암호화 시 12바이트 고유 암호학적 랜덤 논스(Nonce)를 생성하여 결합합니다.
"""

import os
import base64
import hashlib
from typing import Optional
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from core.config import settings

# 32바이트 기본 암호화 키 유도 함수
def _resolve_key(custom_key: Optional[bytes] = None) -> bytes:
    if custom_key is not None:
        if len(custom_key) == 32:
            return custom_key
        return hashlib.sha256(custom_key).digest()
    
    configured_key = getattr(settings, "ACTION_CARD_ENCRYPTION_KEY", "")
    if configured_key:
        return hashlib.sha256(configured_key.encode("utf-8")).digest()
    
    fallback_seed = (
        getattr(settings, "SUPABASE_JWT_SECRET", "")
        or getattr(settings, "DATABASE_URL", "iching-default-secure-salt")
    )
    return hashlib.sha256(f"iching-action-card-aes256:{fallback_seed}".encode("utf-8")).digest()


def encrypt_sensitive_field(plain_text: str, key: Optional[bytes] = None) -> bytes:
    """
    AES-256-GCM 알고리즘으로 민감정보 텍스트를 암호화합니다.
    반환값: 12바이트 nonce + 암호문(태그 포함) 바이너리
    """
    if not plain_text:
        return b""
    aes_key = _resolve_key(key)
    aesgcm = AESGCM(aes_key)
    nonce = os.urandom(12)  # GCM 표준 12바이트 암호학적 논스
    ciphertext = aesgcm.encrypt(nonce, plain_text.encode("utf-8"), None)
    return nonce + ciphertext


def decrypt_sensitive_field(encrypted_bytes: bytes, key: Optional[bytes] = None) -> str:
    """
    GCM 암호문에서 앞 12바이트 nonce를 분리하여 원본 데이터를 안전하게 복호화합니다.
    """
    if not encrypted_bytes:
        return ""
    if len(encrypted_bytes) <= 12:
        raise ValueError("유효하지 않은 암호문 바이트 길이입니다 (최소 12바이트 초과 필요).")
    
    aes_key = _resolve_key(key)
    aesgcm = AESGCM(aes_key)
    nonce = encrypted_bytes[:12]
    ciphertext = encrypted_bytes[12:]
    decrypted_data = aesgcm.decrypt(nonce, ciphertext, None)
    return decrypted_data.decode("utf-8")


def encrypt_to_base64(plain_text: str, key: Optional[bytes] = None) -> str:
    """JSON 직렬화 및 API 통신을 위해 암호화된 바이너리를 Base64 문자열로 반환합니다."""
    encrypted_bytes = encrypt_sensitive_field(plain_text, key)
    if not encrypted_bytes:
        return ""
    return base64.b64encode(encrypted_bytes).decode("utf-8")


def decrypt_from_base64(b64_string: str, key: Optional[bytes] = None) -> str:
    """Base64 문자열을 디코딩하여 AES-256-GCM으로 복호화합니다."""
    if not b64_string:
        return ""
    encrypted_bytes = base64.b64decode(b64_string.encode("utf-8"))
    return decrypt_sensitive_field(encrypted_bytes, key)
