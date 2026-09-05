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
