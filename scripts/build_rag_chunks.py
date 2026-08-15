"""4단계 RAG 청크 원본을 data/hexagrams.json에서 뽑는다.

    python scripts/build_rag_chunks.py -o data/rag_chunks.json

무엇을 넣고 빼는지는 CLAUDE.md의 데이터 레이어 표가 정한다(2026-08-14 확정).
  넣는다  정전 주석 전부, 소상전·단전·대상전 원문
  뺀다    괘사·효사 원문 — focus_rule이 가리키는 대로 DB에서 1:1로 꺼내야 한다.
          의미 검색으로 찾으면 엉뚱한 괘의 괘사가 붙는다.
  뺀다    문언전 — 건·곤 두 괘에만 있어 그 두 괘만 근거가 두꺼워진다.
  뺀다    계사전·설괘전·서괘전·잡괘전 — 특정 괘에 붙지 않는 일반론이다.
          애초에 파서가 잘라내므로 이 파일에는 들어오지도 않는다.

청크 id는 재실행해도 같아야 한다. 임베딩을 다시 만들 때 무엇이 바뀌었는지
대조해야 하기 때문이다.
"""
import argparse
import json
import os
import sys
from typing import Any, Dict, List

sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), "..")))


def build(hexagrams: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    chunks: List[Dict[str, Any]] = []

    def add(hid, line_no, category, source_type, text, seq=0):
        text = (text or "").strip()
        if not text:
            return
        pos = line_no if line_no is not None else 0
        chunks.append({
            "id": f"C{hid}-{source_type}-{pos}-{seq}",
            "hexagram_id": hid,
            "line_number": line_no,
            "category": category,
            "source_type": source_type,
            "content": text,
        })

    for h in hexagrams:
        hid = h["hexagram_id"]

        # 괘 단위
        # 序卦 해설은 괘사 주석과 따로 센다. 각 괘에 1:1로 붙으므로 계사전처럼
        # 빼지는 않지만, "이 괘가 왜 이 자리인가"를 논하는 글이라 상황 매핑에
        # 쓰는 괘사 주석과는 쓰임이 다르다. 나중에 가중치를 달리 주거나 빼려면
        # 지금 갈라두어야 한다.
        for i, c in enumerate(h.get("intro") or []):
            add(hid, None, "annotation", "gwa_intro", c, i)

        for i, c in enumerate(h["guasa"]["commentary"]):
            add(hid, None, "annotation", "guasa_comm", c, i)

        add(hid, None, "canon", "tanjon", h["danjeon"]["original"])
        for i, c in enumerate(h["danjeon"]["commentary"]):
            add(hid, None, "annotation", "tanjon_comm", c, i)

        add(hid, None, "canon", "daesang", h["daesang"]["original"])
        for i, c in enumerate(h["daesang"]["commentary"]):
            add(hid, None, "annotation", "daesang_comm", c, i)

        # 문언전은 넣지 않는다 (h["munon"])

        # 효 단위
        for line in h["lines"]:
            pos = line["position"]
            for i, c in enumerate(line["commentary"]):
                add(hid, pos, "annotation", "line_comm", c, i)
            add(hid, pos, "canon", "sosang", line.get("sosang"))
            for i, c in enumerate(line.get("sosang_commentary") or []):
                add(hid, pos, "annotation", "sosang_comm", c, i)

    return chunks


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-i", "--input", default="data/hexagrams.json",
                    help="괘 구조 JSON. Kanripo 이관본은 data/hexagrams_kanripo.json")
    ap.add_argument("-o", "--output", default="data/rag_chunks.json")
    args = ap.parse_args()

    root = os.path.realpath(os.path.join(os.path.dirname(__file__), ".."))
    src = args.input if os.path.isabs(args.input) else os.path.join(root, args.input)
    hexagrams = json.load(open(src, encoding="utf-8"))
    chunks = build(hexagrams)

    assert len(chunks) == len({c["id"] for c in chunks}), "청크 id 중복"
    assert all(c["content"] for c in chunks), "내용이 빈 청크가 있다"
    # 괘사·효사 원문이 새어 들어오면 여기서 막는다
    canon_sources = {c["source_type"] for c in chunks if c["category"] == "canon"}
    assert canon_sources <= {"tanjon", "daesang", "sosang"}, f"넣으면 안 되는 원문: {canon_sources}"

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)

    from collections import Counter
    by_type = Counter(c["source_type"] for c in chunks)
    lengths = sorted(len(c["content"]) for c in chunks)
    print(f"{len(chunks)}건 생성 → {args.output}")
    for t, n in sorted(by_type.items(), key=lambda x: -x[1]):
        print(f"  {t:14} {n:5}")
    print(f"  길이 중앙값 {lengths[len(lengths)//2]}자 / 최장 {lengths[-1]}자")


if __name__ == "__main__":
    main()
