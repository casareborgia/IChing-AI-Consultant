"""효사·괘사의 판정 어법을 분류한다 — 조건부인가 단정인가.

    python scripts/classify_verdict_modality.py -o data/verdict_modality.json

왜 필요한가. 주역의 판정(吉凶咎吝悔厲)은 대개 "너는 흉하다"가 아니라
"이런 형세면 흉하다"이다. 조건부인 자리에서는 상담 문장이 뒤집을 여지를
말할 수 있다 — "밀고 나가면 흉하다"는 "밀고 나가지만 않으면 거기까지는
가지 않는다"로 되받을 수 있다. 이것이 예언이 아니라 상담이 되는 지점이다.

그러나 정전조차 조건을 붙이지 않고 곧바로 흉하다고 하는 자리가 있다.
거기서 억지로 조건을 붙이면 그건 원문 왜곡이다. 그래서 미리 갈라 둔다.

분류
  conditional_text  원문에 조건 표지(면/어든/則)와 판정어가 함께 있다
  conditional_comm  원문엔 없으나 정전 주석이 조건을 되살려 푼다
  unmarked          조건 표지가 없다. 주석도 조건을 되살리지 않는다
  none              판정어 자체가 없다

주의 — unmarked는 "단정"이 아니다. 표지가 없을 뿐 대부분 [형세]→[판정] 꼴이라
실질은 조건부다(`貞이라 吉리니` = 곧게 지키면 길하다). 진짜 단정, 곧 되돌릴 수
없는 일이 이미 벌어진 자리(`剝牀以膚니 凶` — 벗김이 살갗까지 왔다)는 그중
일부다. 이 구분은 문법이 아니라 뜻에서 갈려 정규식으로는 나눌 수 없다.
상담 문장을 고를 때는 unmarked를 사람이나 모델이 한 번 더 갈라야 한다.
"""
import argparse
import asyncio
import json
import os
import re
import sys
from collections import Counter
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import select

from core.db import AsyncSessionLocal
from core.models.hexagram import Hexagram, Line
from core.models.rag import InterpretationChunk

# 현토의 조건 표지와 한문의 則
COND_SRC = re.compile(r"면|어든|커든|則")
# 판정어. 无咎·无悔도 咎·悔로 잡힌다
VERDICT_SRC = re.compile(r"[吉凶咎吝悔厲]")

# 번역문에서 조건을 되살렸는지 볼 때 쓰는 표지
COND_KO = re.compile(r"(으면|하면|이면|거든|어든)")
VERDICT_KO = re.compile(r"(흉|길하|길함|허물|뉘우침|부끄러|위태)")


def restores_condition(commentary: str) -> Optional[str]:
    """주석 문장 중 '…면 … 흉/길' 꼴이 있으면 그 문장을 돌려준다.

    문장 단위로 본다. 글 전체에 '면'과 '흉'이 흩어져 있는 것만으로는
    조건을 되살렸다고 볼 수 없다.
    """
    for sent in re.split(r"(?<=다)\.\s*|\.\s+", commentary):
        m = VERDICT_KO.search(sent)
        if not m:
            continue
        # 판정어 앞쪽에 조건 표지가 있어야 한다
        if COND_KO.search(sent[:m.start()]):
            return sent.strip()
    return None


async def collect() -> List[Dict[str, Any]]:
    async with AsyncSessionLocal() as session:
        hexes = {h.id: h for h in (await session.execute(select(Hexagram))).scalars().all()}
        lines = (await session.execute(select(Line))).scalars().all()
        chunks = (await session.execute(
            select(InterpretationChunk).where(
                InterpretationChunk.source_type.in_(["line_comm", "guasa_comm"]))
        )).scalars().all()

    comm: Dict[str, List[str]] = {}
    for c in chunks:
        key = f"L{c.hexagram_id}-{c.line_number}" if c.source_type == "line_comm" else f"H{c.hexagram_id}"
        comm.setdefault(key, []).append(c.content_ko or "")

    rows: List[Dict[str, Any]] = []

    def add(key, hid, pos, source, ko):
        has_verdict = bool(VERDICT_SRC.search(source))
        has_cond = bool(COND_SRC.search(source))
        entry = {
            "id": key,
            "hexagram_id": hid,
            "name_hanja": hexes[hid].name_hanja,
            "line_number": pos,
            "source": source,
            "translation_ko": ko,
        }
        if not has_verdict:
            entry.update(modality="none", evidence=None)
        elif has_cond:
            entry.update(modality="conditional_text",
                         evidence=COND_SRC.search(source).group())
        else:
            restored = None
            for c in comm.get(key, []):
                restored = restores_condition(c)
                if restored:
                    break
            if restored:
                entry.update(modality="conditional_comm", evidence=restored[:120])
            else:
                entry.update(modality="unmarked", evidence=None)
        rows.append(entry)

    for h in hexes.values():
        add(f"H{h.id}", h.id, None, h.judgment_text, h.judgment_ko)
    for l in sorted(lines, key=lambda x: (x.hexagram_id, x.line_number)):
        add(f"L{l.hexagram_id}-{l.line_number}", l.hexagram_id, l.line_number,
            l.statement_text, l.statement_ko)
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--output", default="data/verdict_modality.json")
    args = ap.parse_args()

    rows = asyncio.run(collect())
    lines = [r for r in rows if r["line_number"] is not None]
    guas = [r for r in rows if r["line_number"] is None]
    assert len(lines) == 386 and len(guas) == 64, f"효 {len(lines)} / 괘 {len(guas)}"

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

    for label, group in (("효사 386", lines), ("괘사 64", guas)):
        c = Counter(r["modality"] for r in group)
        verdict = len(group) - c["none"]
        cond = c["conditional_text"] + c["conditional_comm"]
        print(f"\n{label} — 판정어 있는 것 {verdict}건")
        print(f"  조건부 확정        {cond:3}건 ({cond / verdict * 100:.0f}%)")
        print(f"    원문에 조건       {c['conditional_text']:3}")
        print(f"    주석이 조건 복원   {c['conditional_comm']:3}")
        print(f"  표지 없음(재분류 필요) {c['unmarked']:3}건 ({c['unmarked'] / verdict * 100:.0f}%)")
        print(f"  판정어 없음        {c['none']:3}건")

    print(f"\n→ {args.output}")


if __name__ == "__main__":
    main()
