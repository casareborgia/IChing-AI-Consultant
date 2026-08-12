import asyncio
import json
import os
import sys

# Add project root directory to sys.path
sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import select
from core.db import AsyncSessionLocal
from core.models.hexagram import Hexagram, Line

# 64괘 표준 한글 명칭 맵: hexagram_id -> (name_ko, name_full)
HEXAGRAM_NAME_MAP = {
    1: ("건", "중천건"), 2: ("곤", "중지곤"), 3: ("준", "수뢰준"), 4: ("몽", "산수몽"),
    5: ("수", "수천수"), 6: ("송", "천수송"), 7: ("사", "지수사"), 8: ("비", "수지비"),
    9: ("소축", "풍천소축"), 10: ("리", "천택리"), 11: ("태", "지천태"), 12: ("비", "천지비"),
    13: ("동인", "천화동인"), 14: ("대유", "화천대유"), 15: ("겸", "지산겸"), 16: ("예", "뇌지예"),
    17: ("수", "택뢰수"), 18: ("고", "산풍고"), 19: ("임", "지택임"), 20: ("관", "풍지관"),
    21: ("서합", "화뢰서합"), 22: ("비", "산화비"), 23: ("박", "산지박"), 24: ("복", "지뢰복"),
    25: ("무망", "천뢰무망"), 26: ("대축", "산천대축"), 27: ("이", "산뢰이"), 28: ("대과", "택풍대과"),
    29: ("감", "중수감"), 30: ("리", "중화리"), 31: ("함", "택산함"), 32: ("항", "뇌풍항"),
    33: ("둔", "천산둔"), 34: ("대장", "뇌천대장"), 35: ("진", "화지진"), 36: ("명이", "지화명이"),
    37: ("가인", "풍화가인"), 38: ("규", "화택규"), 39: ("건", "수산건"), 40: ("해", "뇌수해"),
    41: ("손", "산택손"), 42: ("익", "풍뢰익"), 43: ("쾌", "택천쾌"), 44: ("구", "천풍구"),
    45: ("췌", "택지췌"), 46: ("승", "지풍승"), 47: ("곤", "택수곤"), 48: ("정", "수풍정"),
    49: ("혁", "택화혁"), 50: ("정", "화풍정"), 51: ("진", "중뇌진"), 52: ("간", "중산간"),
    53: ("점", "풍산점"), 54: ("귀매", "뇌택귀매"), 55: ("풍", "뇌화풍"), 56: ("여", "화산여"),
    57: ("손", "중풍손"), 58: ("태", "중택태"), 59: ("환", "풍수환"), 60: ("절", "수택절"),
    61: ("중부", "풍택중부"), 62: ("소과", "뇌산소과"), 63: ("기제", "수화기제"), 64: ("미제", "화수미제")
}


def compute_binary_code(lines_list: list) -> str:
    """lines 목록의 position 1~6효의 양(1)/음(0) 정보로부터 6자리 이진코드 생성"""
    code_bits = ['0'] * 6
    for line in lines_list:
        pos = line.get("position")
        if 1 <= pos <= 6:
            orig = line.get("original", "").strip()
            # 앞 4글자 내에 '九'가 있으면 1(양), 없으면 0(음)
            prefix = orig[:4]
            if "九" in prefix:
                code_bits[pos - 1] = '1'
            else:
                code_bits[pos - 1] = '0'
    return "".join(code_bits)


async def seed_hexagrams():
    json_path = os.path.join(os.path.dirname(__file__), "..", "data", "hexagrams.json")
    if not os.path.exists(json_path):
        print(f"Error: {json_path} not found.")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        hexagrams_data = json.load(f)

    async with AsyncSessionLocal() as session:
        hex_count = 0
        line_count = 0

        for hex_item in hexagrams_data:
            hid = hex_item["hexagram_id"]
            name_ko, name_full = HEXAGRAM_NAME_MAP.get(hid, (f"괘_{hid}", f"괘_{hid}"))
            lines_data = hex_item.get("lines", [])
            binary_code = compute_binary_code(lines_data)

            guasa_orig = hex_item.get("guasa", {}).get("original", "")
            danjeon_orig = hex_item.get("danjeon", {}).get("original", "")
            daesang_orig = hex_item.get("daesang", {}).get("original", "")
            munon_orig = hex_item.get("munon", {}).get("original", "")

            # 기존 괘 레코드 존재 여부 확인
            stmt = select(Hexagram).where(Hexagram.id == hid)
            existing_hex = (await session.execute(stmt)).scalar_one_or_none()

            if existing_hex:
                hex_obj = existing_hex
                hex_obj.binary_code = binary_code
                hex_obj.symbol = hex_item.get("symbol", "")
                hex_obj.name_ko = name_ko
                hex_obj.name_hanja = hex_item.get("name_hanja", "")
                hex_obj.name_full = name_full
                hex_obj.judgment_text = guasa_orig
                hex_obj.tanjon_text = danjeon_orig
                hex_obj.xiang_text = daesang_orig
                hex_obj.wenyan_text = munon_orig
            else:
                hex_obj = Hexagram(
                    id=hid,
                    binary_code=binary_code,
                    symbol=hex_item.get("symbol", ""),
                    name_ko=name_ko,
                    name_hanja=hex_item.get("name_hanja", ""),
                    name_full=name_full,
                    judgment_text=guasa_orig,
                    tanjon_text=danjeon_orig,
                    xiang_text=daesang_orig,
                    wenyan_text=munon_orig,
                )
                session.add(hex_obj)

            hex_count += 1

            # Lines 적재
            for line_item in lines_data:
                pos = line_item.get("position")
                stmt_line = select(Line).where(Line.hexagram_id == hid, Line.line_number == pos)
                existing_line = (await session.execute(stmt_line)).scalar_one_or_none()

                stmt_text = line_item.get("original", "")
                sosang_text = line_item.get("sosang", "")

                if existing_line:
                    existing_line.statement_text = stmt_text
                    existing_line.small_xiang_text = sosang_text
                else:
                    line_obj = Line(
                        hexagram_id=hid,
                        line_number=pos,
                        statement_text=stmt_text,
                        small_xiang_text=sosang_text,
                    )
                    session.add(line_obj)

                line_count += 1

        await session.commit()
        print(f"Successfully seeded {hex_count} hexagrams and {line_count} lines to DB.")


if __name__ == "__main__":
    asyncio.run(seed_hexagrams())
