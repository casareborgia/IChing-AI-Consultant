# -*- coding: utf-8 -*-
"""
서버 사이드 카드 래스터화(EXIF 세척) 및 API 엔드포인트 단위 테스트
"""

import io
import pytest
from PIL import Image
from core.card_image import CardImageRenderer
from agents.action_card_generator_v2 import ActionCardGeneratorV2


def test_render_normal_action_card():
    renderer = CardImageRenderer()
    card_data = {
        "is_crisis": False,
        "universe_transition": "천지비(12)에서 화뢰서합(21)으로 오르는 마음의 정돈",
        "sacred_metaphor": "九五 休否，大人吉。其亡其亡，繫于苞桑。",
        "client_aha_moment": "후배의 부탁을 거절하지 못했던 나의 불안과 인정 욕구를 인정하고 내려놓다.",
        "client_action_pledge": "오늘 오후 4시에 후배에게 단호하지만 예의 바른 어조로 나의 원칙을 설명하겠다.",
        "counselor_reframing": "당신의 원칙과 고결한 뜻을 지켜내는 용기 있는 실천을 온 힘으로 지지합니다."
    }

    stream = renderer.render_card_png(card_data)
    assert isinstance(stream, io.BytesIO)

    stream.seek(0)
    img_bytes = stream.getvalue()

    # PNG 시그니처 바이트 검증: \x89PNG\r\n\x1a\n
    assert img_bytes.startswith(b"\x89PNG\r\n\x1a\n")

    # Pillow 이미지 파싱 및 해상도/RGB 모드 검증
    stream.seek(0)
    with Image.open(stream) as img:
        assert img.size == (1080, 1520)
        assert img.mode == "RGB"
        # EXIF 메타데이터 부재 검증
        exif = img.getexif()
        assert len(exif) == 0


def test_render_crisis_spi_card():
    renderer = CardImageRenderer()
    card_data = {
        "is_crisis": True,
        "crisis_warning_signs": "극심한 고통 및 '사라지고 싶다' 징후 감지",
        "inner_coping_strategies": [
            "4-7-8 호흡으로 심박수 안정화",
            "5-4-3-2-1 오감 접지 훈련으로 현실 감각 회복"
        ],
        "emergency_professional_agencies": [
            "정신건강 위기상담전화: 109",
            "긴급 생명 구조: 119 및 112"
        ]
    }

    stream = renderer.render_card_png(card_data)
    stream.seek(0)
    with Image.open(stream) as img:
        assert img.size == (1080, 1520)
        assert img.mode == "RGB"


def test_action_card_generator_v2_encryption_integration():
    generator = ActionCardGeneratorV2()
    llm_payload = {
        "universe_transition": "정돈의 여정",
        "sacred_metaphor": "본질을 지키는 일",
        "client_aha_moment": "나의 아집을 내려놓다",
        "client_action_pledge": "10분 실천 행동",
        "counselor_reframing": "격려와 지지",
        "is_smart_compliant": True
    }

    schema = generator.build_full_schema(llm_payload)
    sec_ops = schema.get("security_ops", {})

    assert sec_ops.get("encryption") == "AES-256"
    assert sec_ops.get("exif_purged") is True
    assert "encrypted_aha_moment" in sec_ops
    assert "encrypted_action_pledge" in sec_ops
    assert len(sec_ops["encrypted_aha_moment"]) > 0
    assert len(sec_ops["encrypted_action_pledge"]) > 0

    # 래스터화 스트림도 정상 동작하는지 확인
    stream = generator.render_card_png(llm_payload)
    assert stream.getvalue().startswith(b"\x89PNG")


# --- CYCLE-00-R2: 카드 서버 인증 (P1-3) ---

import time as _time

import jwt as _jwt
from fastapi.testclient import TestClient as _TestClient

from api import deps as _deps
from core.config import settings as _settings


def _client():
    import api.main as _main

    return _TestClient(_main.app)


def _valid_token():
    secret = _settings.SUPABASE_JWT_SECRET or "test-secret"
    _settings.SUPABASE_JWT_SECRET = secret
    return _jwt.encode(
        {
            "sub": "card-user-1",
            "aud": "authenticated",
            "iss": _deps.expected_issuer(),
            "exp": int(_time.time()) + 600,
        },
        secret,
        algorithm="HS256",
    )


_SAMPLE_CARD = {"is_crisis": False, "sacred_metaphor": "바람이 지나간 자리"}


def _reset_limits():
    _deps._request_records.clear()
    _deps._user_records.clear()


def test_card_export_requires_auth():
    """인증 없는 직접 호출은 401이어야 한다. 이전에는 인증이 아예 없었다."""
    _reset_limits()
    res = _client().post("/api/counsel/card/export", json={"card_data": _SAMPLE_CARD})
    assert res.status_code == 401


def test_card_export_rejects_tampered_token():
    _reset_limits()
    token = _valid_token() + "tampered"
    res = _client().post(
        "/api/counsel/card/export",
        json={"card_data": _SAMPLE_CARD},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 401


def test_card_export_rejects_foreign_issuer():
    _reset_limits()
    secret = _settings.SUPABASE_JWT_SECRET or "test-secret"
    _settings.SUPABASE_JWT_SECRET = secret
    token = _jwt.encode(
        {
            "sub": "x",
            "aud": "authenticated",
            "iss": "https://attacker.supabase.co/auth/v1",
            "exp": int(_time.time()) + 600,
        },
        secret,
        algorithm="HS256",
    )
    res = _client().post(
        "/api/counsel/card/export",
        json={"card_data": _SAMPLE_CARD},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 401


class _FakeResult:
    def __init__(self, mapping):
        self._mapping = mapping

    def mappings(self):
        class _Mappings:
            def __init__(self, m):
                self._m = m
            def first(self):
                return self._m
        return _Mappings(self._mapping)


class _FakeAsyncSession:
    def __init__(self, mapping):
        self.mapping = mapping

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def execute(self, *args, **kwargs):
        return _FakeResult(self.mapping)


def test_card_export_succeeds_with_valid_auth(monkeypatch):
    """정상 인증 및 본인 세션에 card_data가 있으면 200 및 PNG 반환."""
    import core.db
    monkeypatch.setattr(core.db, "AsyncSessionLocal", lambda: _FakeAsyncSession({"card_data": _SAMPLE_CARD}))
    _reset_limits()
    res = _client().post(
        "/api/counsel/card/export",
        json={"session_id": "00000000-0000-0000-0000-000000000001"},
        headers={"Authorization": f"Bearer {_valid_token()}"},
    )
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/png"
    assert res.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_card_export_accepts_real_journal_data_payload(monkeypatch):
    """실제 journal_data 형태의 DB 저장분을 정상적으로 렌더링한다."""
    import core.db
    payload = {
        "is_crisis": False,
        "universe_transition": "관계의 매듭을 풀어가는 국면",
        "sacred_metaphor": "가족 안에서 역할을 살핌",
        "client_aha_moment": "엄격함과 방임 사이의 균형",
        "client_action_pledge": "이번 주에 한 번 먼저 안부를 묻는다",
        "counselor_reframing": "당신의 뜻을 응원합니다",
        # CardData 외 부가 키들이 포함되어 있어도 정상 렌더링
        "card_id": "card-abc",
        "card_markdown": "# 카드",
        "card_metadata": {"v": 2},
        "encrypted_action_pledge": "…",
        "juyeok_structure": {"line_value": 9},
        "psychological_engine": "ACT",
        "exif_purged": True,
    }
    monkeypatch.setattr(core.db, "AsyncSessionLocal", lambda: _FakeAsyncSession({"card_data": payload}))
    _reset_limits()
    res = _client().post(
        "/api/counsel/card/export",
        json={"session_id": "00000000-0000-0000-0000-000000000001"},
        headers={"Authorization": f"Bearer {_valid_token()}"},
    )
    assert res.status_code == 200
    assert res.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_card_export_returns_404_when_session_not_found_or_not_owned(monkeypatch):
    """세션이 없거나 타인 세션이면 404 은닉."""
    import core.db
    monkeypatch.setattr(core.db, "AsyncSessionLocal", lambda: _FakeAsyncSession(None))
    _reset_limits()
    res = _client().post(
        "/api/counsel/card/export",
        json={"session_id": "00000000-0000-0000-0000-000000000002"},
        headers={"Authorization": f"Bearer {_valid_token()}"},
    )
    assert res.status_code == 404


def test_card_export_returns_404_when_card_data_is_null(monkeypatch):
    """card_data가 NULL인 과거 세션이면 404."""
    import core.db
    monkeypatch.setattr(core.db, "AsyncSessionLocal", lambda: _FakeAsyncSession({"card_data": None}))
    _reset_limits()
    res = _client().post(
        "/api/counsel/card/export",
        json={"session_id": "00000000-0000-0000-0000-000000000003"},
        headers={"Authorization": f"Bearer {_valid_token()}"},
    )
    assert res.status_code == 404
