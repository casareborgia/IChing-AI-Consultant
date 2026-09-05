# -*- coding: utf-8 -*-
"""
AES-256-GCM 민감정보 암호화/복호화 단위 테스트
"""

import pytest
from core.crypto import (
    encrypt_sensitive_field,
    decrypt_sensitive_field,
    encrypt_to_base64,
    decrypt_from_base64,
)


def test_encrypt_decrypt_roundtrip():
    original_text = "규모의 무조건적인 팽창 욕심과 타인의 시선에 부합하고 싶었던 본질 외적인 아집을 내려놓기로 깨달음"
    encrypted = encrypt_sensitive_field(original_text)

    # 12바이트 논스 + 암호문이므로 원문보다 길어야 함
    assert len(encrypted) > 12
    assert encrypted != original_text.encode("utf-8")

    decrypted = decrypt_sensitive_field(encrypted)
    assert decrypted == original_text


def test_base64_roundtrip():
    action_pledge = "나는 오늘 밤 8시에 매장의 2호점 재료 퀄리티 유지를 보장할 수 있는 주방 동선 설계도를 스케치하겠다."
    b64_enc = encrypt_to_base64(action_pledge)

    assert isinstance(b64_enc, str)
    assert len(b64_enc) > 0

    decrypted = decrypt_from_base64(b64_enc)
    assert decrypted == action_pledge


def test_tampered_ciphertext_fails():
    original_text = "비밀 상담 성찰 내용"
    encrypted = encrypt_sensitive_field(original_text)

    # 암호문 바이트를 하나 변조
    tampered = bytearray(encrypted)
    tampered[-1] ^= 0xFF

    with pytest.raises(Exception):
        decrypt_sensitive_field(bytes(tampered))


def test_empty_string_handling():
    assert encrypt_sensitive_field("") == b""
    assert decrypt_sensitive_field(b"") == ""
    assert encrypt_to_base64("") == ""
    assert decrypt_from_base64("") == ""
