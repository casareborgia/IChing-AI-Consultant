# -*- coding: utf-8 -*-
"""
주역 상담 앱 - 서버 사이드 카드 이미지 래스터화 렌더러 (CardImageRenderer)
- 모바일 인앱 브라우저(카카오톡, 인스타그램 등) 및 구형 기기에서 브라우저 Canvas 다운로드 실패를 방지합니다.
- Pillow(PIL)를 통해 한지 질감 및 고해상도(1080x1520) 순수 RGB 픽셀 래스터화를 온더플라이로 수행합니다.
- 개인정보 보호를 위해 EXIF 및 카메라/기기 메타데이터가 영구 세척된 순수 바이너리 PNG 바이트스트림을 생성합니다.
"""

import os
import io
import textwrap
from typing import Dict, Any, Optional, Tuple, List
from PIL import Image, ImageDraw, ImageFont


class CardImageRenderer:
    """EXIF 세척 순수 래스터화 카드 이미지 생성기"""

    def __init__(self):
        self.width = 1080
        self.height = 1520
        self._font_cache = {}

    def _resolve_font(self, size: int) -> ImageFont.ImageFont:
        """OS별 사용 가능한 한글 폰트를 안전하게 로드합니다."""
        if size in self._font_cache:
            return self._font_cache[size]

        font_candidates = [
            # macOS 시스템 폰트
            "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
            "/Library/Fonts/NanumGothic.ttf",
            "/Library/Fonts/NanumBarunGothic.ttf",
            "/System/Library/Fonts/AppleSDGothicNeo.ttc",
            # Linux 시스템 폰트
            "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
            "/usr/share/fonts/truetype/nanum/NanumBarunGothic.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]

        loaded_font = None
        for path in font_candidates:
            if os.path.exists(path):
                try:
                    loaded_font = ImageFont.truetype(path, size)
                    break
                except Exception:
                    continue

        if loaded_font is None:
            # 최종 폴백 (기본 폰트)
            try:
                loaded_font = ImageFont.load_default(size=size)
            except TypeError:
                loaded_font = ImageFont.load_default()

        self._font_cache[size] = loaded_font
        return loaded_font

    def _draw_wrapped_text(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        x: int,
        y: int,
        max_chars: int,
        font: ImageFont.ImageFont,
        fill: Tuple[int, int, int],
        line_spacing: int = 12,
    ) -> int:
        """줄바꿈을 적용하여 텍스트를 그리고 끝난 Y 좌표를 반환합니다."""
        lines = textwrap.wrap(text, width=max_chars)
        current_y = y
        for line in lines:
            draw.text((x, current_y), line, fill=fill, font=font)
            try:
                bbox = font.getbbox(line)
                line_height = bbox[3] - bbox[1]
            except Exception:
                line_height = 28
            current_y += line_height + line_spacing
        return current_y

    def render_card_png(self, card_data: Dict[str, Any]) -> io.BytesIO:
        """
        카드 딕셔너리 데이터를 받아 순수 래스터화된 PNG 바이너리(BytesIO)를 반환합니다.
        EXIF 메타데이터가 전혀 기록되지 않습니다.
        """
        is_crisis = bool(card_data.get("is_crisis", False))

        # 배경 및 테두리 색상 (한지 톤 vs 위기 안심 톤)
        if is_crisis:
            bg_color = (254, 246, 246)       # 부드러운 핑크 베이지
            border_color1 = (220, 100, 100)  # 외곽 강조선
            border_color2 = (240, 180, 180)  # 내부 섬세선
            tag_color = (200, 40, 40)
            tag_text = "🚨 마음 안전 안심 카드 (Stanley-Brown SPI)"
        else:
            bg_color = (248, 246, 240)       # 부드러운 전통 한지 톤
            border_color1 = (180, 150, 110)  # 앤틱 골드/브론즈 테두리
            border_color2 = (225, 215, 195)  # 엷은 한지 프레임선
            tag_color = (130, 95, 60)
            tag_text = "🎴 마음 전념 카드 (Action Commitment Card)"

        # 1. 캔버스 생성 (순수 RGB, 메타데이터 없음)
        img = Image.new("RGB", (self.width, self.height), color=bg_color)
        draw = ImageDraw.Draw(img)

        # 2. 고급 2중 프레임 테두리
        margin = 35
        draw.rectangle([margin, margin, self.width - margin, self.height - margin], outline=border_color1, width=4)
        draw.rectangle([margin + 12, margin + 12, self.width - margin - 12, self.height - margin - 12], outline=border_color2, width=2)

        # 3. 폰트 준비
        title_font = self._resolve_font(46)
        sub_font = self._resolve_font(26)
        section_label_font = self._resolve_font(30)
        body_font = self._resolve_font(28)
        highlight_font = self._resolve_font(30)
        footer_font = self._resolve_font(22)

        # 4. 헤더 영역 렌더링
        draw.text((80, 80), tag_text, fill=tag_color, font=title_font)
        sub_quote = "지행합일(知行合一) : 내면의 알아차림을 오늘의 구체적 행동으로 잇다"
        draw.text((80, 150), sub_quote, fill=(110, 110, 110), font=sub_font)
        draw.line([80, 205, self.width - 80, 205], fill=border_color2, width=3)

        curr_y = 235
        content_x = 80
        max_chars = 34

        # 5. 섹션별 내용 렌더링
        if is_crisis:
            # [섹션 1] 위기 징후 / 감지된 경고
            draw.text((content_x, curr_y), "⚠️ 마음의 경고 신호 및 위기 징후", fill=(190, 40, 40), font=section_label_font)
            curr_y += 45
            warning_text = card_data.get("crisis_warning_signs") or "극심한 정서적 탈진 및 위기 신호 감지"
            curr_y = self._draw_wrapped_text(draw, warning_text, content_x + 10, curr_y, max_chars, body_font, (60, 60, 60))
            curr_y += 25

            # [섹션 2] 내적 대처법
            draw.text((content_x, curr_y), "🧘 혼자서 실행할 수 있는 내적 대처법", fill=tag_color, font=section_label_font)
            curr_y += 45
            coping = card_data.get("inner_coping_strategies", [])
            coping_text = "\n".join([f"• {c}" for c in coping]) if isinstance(coping, list) else str(coping)
            curr_y = self._draw_wrapped_text(draw, coping_text, content_x + 10, curr_y, max_chars, body_font, (40, 40, 40))
            curr_y += 25

            # [섹션 3] 전문 상담 기관 (109 등)
            draw.text((content_x, curr_y), "📞 24시간 긴급 전문 지원망", fill=(190, 40, 40), font=section_label_font)
            curr_y += 45
            agencies = card_data.get("emergency_professional_agencies", [
                "정신건강 위기상담전화: 109 (24시간 무상 운영)",
                "정신건강센터 상담전화: 1577-0199",
                "긴급 생명 안전 구조: 119 또는 112"
            ])
            agencies_text = "\n".join([f"• {a}" for a in agencies]) if isinstance(agencies, list) else str(agencies)
            curr_y = self._draw_wrapped_text(draw, agencies_text, content_x + 10, curr_y, max_chars, highlight_font, (170, 30, 30))

        else:
            # [섹션 1] 여정의 상(象) & 닻이 될 효사
            universe = card_data.get("universe_transition", "우주적 기운과 마음의 정돈")
            metaphor = card_data.get("sacred_metaphor", "본질을 지키는 일")

            draw.text((content_x, curr_y), "🌌 마음 여정의 궤적 (象)", fill=(120, 95, 65), font=section_label_font)
            curr_y += 45
            curr_y = self._draw_wrapped_text(draw, universe, content_x + 10, curr_y, max_chars, body_font, (50, 50, 50))
            curr_y += 25

            draw.text((content_x, curr_y), "⚓ 성찰의 닻 (효사)", fill=(120, 95, 65), font=section_label_font)
            curr_y += 45
            curr_y = self._draw_wrapped_text(draw, f'"{metaphor}"', content_x + 10, curr_y, max_chars, highlight_font, (40, 40, 40))
            curr_y += 25

            # [섹션 2] 성찰의 눈뜸 (Aha! Moment)
            aha = card_data.get("client_aha_moment", "나의 집착과 불안을 내려놓고 본질을 바라보다.")
            draw.text((content_x, curr_y), "💡 성찰의 눈뜸 (Aha! Moment)", fill=(120, 95, 65), font=section_label_font)
            curr_y += 45
            curr_y = self._draw_wrapped_text(draw, aha, content_x + 10, curr_y, max_chars, body_font, (50, 50, 50))
            curr_y += 25

            # [섹션 3] 오늘 나의 전념 행동 (Committed Action)
            action = card_data.get("client_action_pledge", "오늘 바로 실행할 10분 실천")
            draw.text((content_x, curr_y), "🎯 오늘 나의 전념 행동 (行)", fill=(25, 120, 75), font=section_label_font)
            curr_y += 45
            curr_y = self._draw_wrapped_text(draw, action, content_x + 10, curr_y, max_chars, highlight_font, (20, 110, 65))
            curr_y += 25

            # [섹션 4] 마음의 지지와 격려
            reframing = card_data.get("counselor_reframing", "당신의 고결한 뜻과 실천을 온 마음으로 응원합니다.")
            draw.text((content_x, curr_y), "💬 마음의 지지와 격려", fill=(120, 95, 65), font=section_label_font)
            curr_y += 45
            curr_y = self._draw_wrapped_text(draw, reframing, content_x + 10, curr_y, max_chars, body_font, (80, 80, 80))

        # 6. 하단 푸터 (EXIF 완전 세척 표기 및 브랜딩)
        draw.line([80, self.height - 180, self.width - 80, self.height - 180], fill=border_color2, width=2)
        footer_title = "안티그래비티 주역 심리 상담 웰니스 코치"
        draw.text((80, self.height - 150), footer_title, fill=(140, 140, 140), font=footer_font)
        footer_sub = "※ 본 이미지는 개인정보 및 위치정보 보호를 위해 EXIF 메타데이터가 완전 세척된 순수 래스터 이미지입니다."
        draw.text((80, self.height - 115), footer_sub, fill=(165, 165, 165), font=footer_font)

        # 7. EXIF 없는 순수 PNG 바이너리로 인메모리 스트림 생성
        out_stream = io.BytesIO()
        img.save(out_stream, format="PNG", optimize=True)
        out_stream.seek(0)
        return out_stream
