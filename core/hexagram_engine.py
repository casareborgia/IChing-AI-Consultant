import random
from typing import List, Optional

from schemas.hexagram_engine import (
    BodyUseType,
    FocusRuleResult,
    FocusType,
    HexagramCastResult,
    LineCastResult,
)

# 64괘 이진 코드(초효~상효) -> 괘 ID(1~64) 1:1 매핑 테이블
HEXAGRAM_BINARY_TO_ID = {
    "111111": 1,   # 乾 (중천건)
    "000000": 2,   # 坤 (중지곤)
    "100010": 3,   # 屯 (수뢰준)
    "010001": 4,   # 蒙 (산수몽)
    "111010": 5,   # 需 (수천수)
    "010111": 6,   # 訟 (천수송)
    "010000": 7,   # 師 (지수사)
    "000010": 8,   # 比 (수지비)
    "111011": 9,   # 小畜 (풍천소축)
    "110111": 10,  # 履 (천택리)
    "111000": 11,  # 泰 (지천태)
    "000111": 12,  # 否 (천지비)
    "101111": 13,  # 同人 (천화동인)
    "111101": 14,  # 大有 (화천대유)
    "001000": 15,  # 謙 (지산겸)
    "000100": 16,  # 豫 (뇌지예)
    "100110": 17,  # 隨 (택뢰수)
    "011001": 18,  # 蠱 (산풍고)
    "110000": 19,  # 臨 (지택임)
    "000011": 20,  # 觀 (풍지관)
    "100101": 21,  # 噬嗑 (화뢰서합)
    "101001": 22,  # 賁 (산화비)
    "000001": 23,  # 剝 (산지박)
    "100000": 24,  # 復 (지뢰복)
    "100111": 25,  # 无妄 (천뢰무망)
    "111001": 26,  # 大畜 (산천대축)
    "100001": 27,  # 頤 (산뢰이)
    "011110": 28,  # 大過 (택풍대과)
    "010010": 29,  # 坎 (중수감)
    "101101": 30,  # 離 (중화리)
    "001110": 31,  # 咸 (택산함)
    "011100": 32,  # 恒 (뇌풍항)
    "001111": 33,  # 遯 (천산둔)
    "111100": 34,  # 大壯 (뇌천대장)
    "000101": 35,  # 晉 (화지진)
    "101000": 36,  # 明夷 (지화명이)
    "101011": 37,  # 家人 (풍화가인)
    "110101": 38,  # 睽 (화택규)
    "001010": 39,  # 蹇 (수산건)
    "010100": 40,  # 解 (뇌수해)
    "110001": 41,  # 損 (산택손)
    "100011": 42,  # 益 (풍뢰익)
    "111110": 43,  # 夬 (택천쾌)
    "011111": 44,  # 姤 (천풍구)
    "000110": 45,  # 萃 (택지췌)
    "011000": 46,  # 升 (지풍승)
    "010110": 47,  # 困 (택수곤)
    "011010": 48,  # 井 (수풍정)
    "101110": 49,  # 革 (택화혁)
    "011101": 50,  # 鼎 (화풍정)
    "100100": 51,  # 震 (중뇌진)
    "001001": 52,  # 艮 (중산간)
    "001011": 53,  # 漸 (풍산점)
    "110100": 54,  # 歸妹 (뇌택귀매)
    "101100": 55,  # 豐 (뇌화풍)
    "001101": 56,  # 旅 (화산여)
    "011011": 57,  # 巽 (중풍손)
    "110110": 58,  # 兌 (중택태)
    "010011": 59,  # 渙 (풍수환)
    "110010": 60,  # 節 (수택절)
    "110011": 61,  # 中孚 (풍택중부)
    "001100": 62,  # 小過 (뇌산소과)
    "101010": 63,  # 旣濟 (수화기제)
    "010101": 64,  # 未濟 (화수미제)
}

HEXAGRAM_ID_TO_BINARY = {v: k for k, v in HEXAGRAM_BINARY_TO_ID.items()}

# ---------------------------------------------------------------------------
# 체용(體用) 보완 규칙 상수
# 지괘가 아래 9괘이면 본괘(體) 위주로 해석한다.
# 출처: 주역점치는법, 비(否/12), 점(漸/53), 려(旅/56), 함(咸/31), 미제(未濟/64),
#       곤(困/47), 고(蠱/18), 정(井/48), 항(恒/32)
_BODY_USE_EMPHASIZE_ORIGINAL: frozenset[int] = frozenset({12, 53, 56, 31, 64, 47, 18, 48, 32})

# 지괘가 아래 9괘이면 지괘(用) 위주로 해석한다.
# 익(益/42), 서합(噬嗑/21), 비(賁/22), 기제(旣濟/63), 풍(豊/55),
# 손(損/41), 절(節/60), 귀매(歸妹/54), 태(泰/11)
_BODY_USE_EMPHASIZE_TRANSFORMED: frozenset[int] = frozenset({42, 21, 22, 63, 55, 41, 60, 54, 11})

# 지괘 이름 조회 (체용 주석 생성용) — 괘 ID → 한글 이름
_HEX_NAME_KO: dict[int, str] = {
    11: "지천태(泰)", 12: "천지비(否)", 18: "산풍고(蠱)", 21: "화뢰서합(噬嗑)",
    22: "산화비(賁)", 31: "택산함(咸)", 32: "뇌풍항(恒)", 41: "산택손(損)",
    42: "풍뢰익(益)", 47: "택수곤(困)", 48: "수풍정(井)", 53: "풍산점(漸)",
    54: "뇌택귀매(歸妹)", 55: "뇌화풍(豊)", 56: "화산여(旅)", 60: "수택절(節)",
    63: "수화기제(旣濟)", 64: "화수미제(未濟)",
}
# ---------------------------------------------------------------------------


def binary_to_hexagram_id(binary_code: str) -> int:
    """6자리 이진 코드를 괘 ID(1~64)로 변환"""
    if len(binary_code) != 6 or not set(binary_code).issubset({"0", "1"}):
        raise ValueError(f"유효하지 않은 이진 코드입니다: {binary_code}")
    
    if binary_code not in HEXAGRAM_BINARY_TO_ID:
        raise ValueError(f"매핑되지 않은 괘 이진 코드입니다: {binary_code}")
        
    return HEXAGRAM_BINARY_TO_ID[binary_code]


def hexagram_id_to_binary(hex_id: int) -> str:
    """괘 ID(1~64)를 6자리 이진 코드로 변환"""
    if hex_id not in HEXAGRAM_ID_TO_BINARY:
        raise ValueError(f"유효하지 않은 괘 ID입니다: {hex_id}")
    return HEXAGRAM_ID_TO_BINARY[hex_id]


def cast_single_line(method: str = "coin") -> int:
    """단일 효 수치(6, 7, 8, 9) 생성
    - coin (동전점): 6 (1/8), 7 (3/8), 8 (3/8), 9 (1/8)
    - yarrow (시초점): 6 (1/16), 7 (5/16), 8 (7/16), 9 (3/16)
    """
    rand = random.random()
    if method == "coin":
        if rand < 0.125:
            return 6  # 노음
        elif rand < 0.500:
            return 7  # 소양
        elif rand < 0.875:
            return 8  # 소음
        else:
            return 9  # 노양
    elif method == "yarrow":
        if rand < 0.0625:
            return 6  # 노음 (1/16)
        elif rand < 0.3750:
            return 7  # 소양 (5/16 -> 1/16 + 5/16 = 6/16 = 0.375)
        elif rand < 0.8125:
            return 8  # 소음 (7/16 -> 6/16 + 7/16 = 13/16 = 0.8125)
        else:
            return 9  # 노양 (3/16 -> 13/16 + 3/16 = 1.0)
    else:
        raise ValueError(f"지원하지 않는 점법입니다: {method}")


def _calculate_body_use(transformed_hex_id: Optional[int]) -> tuple[BodyUseType, Optional[str]]:
    """체용(體用) 보완 규칙 판정.

    지괘가 특수 18괘에 해당할 경우 BodyUseType과 한글 설명을 반환한다.
    지괘가 없거나 나머지 46괘이면 (STANDARD, None)을 반환한다.
    """
    if transformed_hex_id is None:
        return BodyUseType.STANDARD, None

    name = _HEX_NAME_KO.get(transformed_hex_id, f"제{transformed_hex_id}괘")

    if transformed_hex_id in _BODY_USE_EMPHASIZE_ORIGINAL:
        note = (
            f"지괘가 {name}이므로, 체용 보완 규칙에 따라 "
            "본괘(體)의 기류를 중심으로 해석의 무게를 둡니다."
        )
        return BodyUseType.EMPHASIZE_ORIGINAL, note

    if transformed_hex_id in _BODY_USE_EMPHASIZE_TRANSFORMED:
        note = (
            f"지괘가 {name}이므로, 체용 보완 규칙에 따라 "
            "지괘(用)의 미래 기운을 중심으로 해석의 무게를 둡니다."
        )
        return BodyUseType.EMPHASIZE_TRANSFORMED, note

    return BodyUseType.STANDARD, None


def calculate_focus_rule(
    original_hex_id: int,
    changing_lines: List[int],
    transformed_hex_id: Optional[int] = None,
) -> FocusRuleResult:
    """주자(朱子) 점법 기준 동효 수(0~6개)에 따른 해석 집중 대상 판단.

    Args:
        original_hex_id: 본괘 ID (1~64)
        changing_lines: 변효(동효) 위치 목록 (1~6)
        transformed_hex_id: 지괘 ID. 체용 보완 규칙 계산에 사용. 없으면 None.
    """
    count = len(changing_lines)
    body_use_type, body_use_note = _calculate_body_use(transformed_hex_id)

    if count == 0:
        return FocusRuleResult(
            focus_type=FocusType.ORIGINAL_JUDGMENT,
            target_hexagram_type="ORIGINAL",
            target_line_numbers=[],
            description_ko="변효가 없으므로 본괘의 괘사(卦辭)를 주 해석으로 삼습니다.",
        )
    elif count == 1:
        return FocusRuleResult(
            focus_type=FocusType.SINGLE_LINE_STATEMENT,
            target_hexagram_type="ORIGINAL",
            target_line_numbers=[changing_lines[0]],
            description_ko=f"1개의 변효가 있으므로 본괘 {changing_lines[0]}효의 효사(爻辭)를 주 해석으로 삼습니다.",
            body_use_type=body_use_type,
            body_use_note_ko=body_use_note,
        )
    elif count == 2:
        # 상위 효 우선
        sorted_lines = sorted(changing_lines, reverse=True)
        return FocusRuleResult(
            focus_type=FocusType.MULTIPLE_LINE_STATEMENTS,
            target_hexagram_type="ORIGINAL",
            target_line_numbers=sorted_lines,
            description_ko=f"2개의 변효가 있으므로 본괘 두 효({sorted_lines[1]}효, {sorted_lines[0]}효)의 효사를 주 해석으로 삼으며, 상위 효({sorted_lines[0]}효)를 우선합니다.",
            body_use_type=body_use_type,
            body_use_note_ko=body_use_note,
        )
    elif count == 3:
        # 주희 《역학계몽》 고변점: 초효(1효) 포함 여부에 따라 본괘/지괘 괘사 분기
        if 1 in changing_lines:
            base = FocusRuleResult(
                focus_type=FocusType.ORIGINAL_JUDGMENT,
                target_hexagram_type="ORIGINAL",
                target_line_numbers=[],
                description_ko=(
                    "3개의 변효 중 초효(1효)가 포함되어 있으므로 "
                    "본괘의 괘사(卦辭)를 주 해석으로 삼습니다."
                ),
            )
        else:
            base = FocusRuleResult(
                focus_type=FocusType.TRANSFORMED_JUDGMENT,
                target_hexagram_type="TRANSFORMED",
                target_line_numbers=[],
                description_ko=(
                    "3개의 변효 중 초효(1효)가 부동효이므로 "
                    "지괘의 괘사(卦辭)를 주 해석으로 삼습니다."
                ),
            )
        body_use_type, body_use_note = _calculate_body_use(transformed_hex_id)
        return base.model_copy(update={
            "body_use_type": body_use_type,
            "body_use_note_ko": body_use_note,
        })
    elif count == 4:
        # 지괘에서 변하지 않은 두 효 중 아래쪽(하위) 효사 우선
        unchanged = sorted([pos for pos in range(1, 7) if pos not in changing_lines])
        return FocusRuleResult(
            focus_type=FocusType.MULTIPLE_LINE_STATEMENTS,
            target_hexagram_type="TRANSFORMED",
            target_line_numbers=unchanged,
            description_ko=f"4개의 변효가 있으므로 지괘에서 변하지 않은 두 효({unchanged[0]}효, {unchanged[1]}효)의 효사를 주 해석으로 삼으며, 아래쪽 효({unchanged[0]}효)를 우선합니다.",
            body_use_type=body_use_type,
            body_use_note_ko=body_use_note,
        )
    elif count == 5:
        # 지괘에서 변하지 않은 1개 효사
        unchanged = [pos for pos in range(1, 7) if pos not in changing_lines][0]
        return FocusRuleResult(
            focus_type=FocusType.SINGLE_LINE_STATEMENT,
            target_hexagram_type="TRANSFORMED",
            target_line_numbers=[unchanged],
            description_ko=f"5개의 변효가 있으므로 지괘에서 변하지 않은 하나의 효({unchanged}효) 효사를 주 해석으로 삼습니다.",
            body_use_type=body_use_type,
            body_use_note_ko=body_use_note,
        )
    elif count == 6:
        # 6개 모두 변함 — 건/곤 특수 예외, 나머지는 지괘 괘사
        # 건/곤은 체용 보완 규칙 대상 외이므로 body_use는 STANDARD로 둔다
        if original_hex_id == 1:
            return FocusRuleResult(
                focus_type=FocusType.SPECIAL_USE_LINE,
                target_hexagram_type="ORIGINAL",
                target_line_numbers=[7],
                description_ko="건괘 6효가 모두 변하였으므로 용구(用九) 효사를 주 해석으로 삼습니다.",
            )
        elif original_hex_id == 2:
            return FocusRuleResult(
                focus_type=FocusType.SPECIAL_USE_LINE,
                target_hexagram_type="ORIGINAL",
                target_line_numbers=[7],
                description_ko="곤괘 6효가 모두 변하였으므로 용육(用六) 효사를 주 해석으로 삼습니다.",
            )
        else:
            # 본괘 괘사는 참작 대상이 아니다. BOTH_JUDGMENTS(3변효)와 반드시 구분되어야 한다.
            return FocusRuleResult(
                focus_type=FocusType.TRANSFORMED_JUDGMENT,
                target_hexagram_type="TRANSFORMED",
                target_line_numbers=[],
                description_ko="6효가 모두 변하였으므로 지괘의 괘사를 주 해석으로 삼습니다.",
                body_use_type=body_use_type,
                body_use_note_ko=body_use_note,
            )
    else:
        raise ValueError(f"유효하지 않은 변효 수입니다: {count}")


def cast_hexagram(
    method: str = "coin",
    manual_lines: Optional[List[int]] = None,
) -> HexagramCastResult:
    """괘 도출 함수
    - method: 'coin' 또는 'yarrow'
    - manual_lines: [6, 7, 8, 9, 7, 8] 과 같이 1효~6효 수치 직접 지정 가능
    """
    if manual_lines is not None:
        if len(manual_lines) != 6 or any(v not in (6, 7, 8, 9) for v in manual_lines):
            raise ValueError(f"manual_lines는 6~9 사이 수치 6개로 구성되어야 합니다: {manual_lines}")
        line_values = list(manual_lines)
    else:
        line_values = [cast_single_line(method=method) for _ in range(6)]

    line_results: List[LineCastResult] = []
    orig_bits: List[str] = []
    trans_bits: List[str] = []
    changing_lines: List[int] = []

    for idx, val in enumerate(line_values):
        pos = idx + 1
        if val == 6:     # 노음 (음 -> 양)
            orig_b = "0"
            trans_b = "1"
            is_chg = True
            changing_lines.append(pos)
        elif val == 7:   # 소양 (양 -> 양)
            orig_b = "1"
            trans_b = "1"
            is_chg = False
        elif val == 8:   # 소음 (음 -> 음)
            orig_b = "0"
            trans_b = "0"
            is_chg = False
        elif val == 9:   # 노양 (양 -> 음)
            orig_b = "1"
            trans_b = "0"
            is_chg = True
            changing_lines.append(pos)

        orig_bits.append(orig_b)
        trans_bits.append(trans_b)
        line_results.append(
            LineCastResult(
                position=pos,
                value=val,
                original_bit=orig_b,
                is_changing=is_chg,
                transformed_bit=trans_b,
            )
        )

    orig_binary = "".join(orig_bits)
    orig_hex_id = binary_to_hexagram_id(orig_binary)

    if changing_lines:
        trans_binary = "".join(trans_bits)
        trans_hex_id = binary_to_hexagram_id(trans_binary)
    else:
        trans_binary = None
        trans_hex_id = None

    focus_rule = calculate_focus_rule(
        original_hex_id=orig_hex_id,
        changing_lines=changing_lines,
        transformed_hex_id=trans_hex_id,
    )

    return HexagramCastResult(
        original_hexagram_id=orig_hex_id,
        original_binary=orig_binary,
        transformed_hexagram_id=trans_hex_id,
        transformed_binary=trans_binary,
        changing_lines=changing_lines,
        lines=line_results,
        focus_rule=focus_rule,
    )


def rebuild_cast(
    original_hexagram_id: int,
    changing_lines: Optional[List[int]] = None,
) -> HexagramCastResult:
    """이미 뽑힌 괘를 그대로 되살린다. 다시 뽑지 않는다.

    본괘 ID와 동효 위치만 있으면 6효의 수치가 하나로 결정된다 — 동효인 양은 9,
    동효인 음은 6, 변하지 않는 양은 7, 음은 8이다. 그래서 세션이 이어질 때
    `cast_hexagram()`을 다시 부를 이유가 없다. 다시 부르면 같은 질문에 새 괘가
    나오고, 그건 재삼독 금지 원칙을 어기는 것이기도 하다.
    """
    binary = hexagram_id_to_binary(original_hexagram_id)
    changing = set(changing_lines or [])

    invalid = [p for p in changing if p not in range(1, 7)]
    if invalid:
        raise ValueError(f"동효 위치는 1~6이어야 합니다: {invalid}")

    line_values: List[int] = []
    for pos in range(1, 7):
        is_yang = binary[pos - 1] == "1"
        if pos in changing:
            line_values.append(9 if is_yang else 6)
        else:
            line_values.append(7 if is_yang else 8)

    return cast_hexagram(manual_lines=line_values)
