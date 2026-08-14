"""표지 없는 91건을 뜻으로 가른다 — 바꿀 수 있는 형세인가, 이미 벌어진 일인가.

    python scripts/judge_verdict_modality.py -o data/verdict_modality_judgments.json

`classify_verdict_modality.py`가 문법으로 가를 수 있는 데까지 간 뒤 남긴 것들이다.
여기서부터는 뜻을 봐야 해서 모델에 묻는다. 다만 근거 없이 묻지 않는다 —
각 항목의 소상전과 정전 주석을 함께 넣는다. 주석가가 그 형세를 어떻게 보았는지가
가장 좋은 근거이기 때문이다.

`unclear`를 허용한다. 애매한 것을 `changeable`로 밀면 없는 여지를 지어내게 되고,
그건 이 작업의 목적과 정반대다.
"""
import argparse
import asyncio
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select

from core.db import AsyncSessionLocal
from core.models.rag import InterpretationChunk
from scripts.translate import ClaudeTranslator, settings

SYSTEM = """당신은 주역 원문의 판정 어법을 분류합니다.

■ 무엇을 보는가
각 항목에는 판정어(吉·凶·咎·吝·悔·厲)가 있습니다. 그 판정 **바로 앞에 놓인 형세**를
보고, 그것이 지금도 바꿀 수 있는 것인지 이미 벌어진 일인지 가르십시오.

  changeable  그 형세가 아직 고르거나 바꿀 수 있는 것이다.
              예: '知臨이니 吉' — 지혜로 임하는 것은 지금 택할 수 있는 태도다.
              예: '貞이라 吉리니' — 곧게 지키는 것은 지금 할 수 있다.

  done        그 형세가 이미 벌어져 되돌릴 수 없다.
              예: '剝牀以膚니 凶' — 벗김이 이미 살갗까지 왔다.
              예: '何校야 滅耳니 凶' — 이미 귀를 잃었다.

  unclear     둘 중 어느 쪽인지 판단이 서지 않는다.

■ 반드시 지킬 것
1. 애매하면 changeable로 밀지 마십시오. 판단이 안 서면 unclear입니다.
   없는 여지를 지어내는 것이 이 작업에서 가장 나쁜 실패입니다.
2. 길한 판정도 똑같이 봅니다. '吉'이라고 다 changeable이 아닙니다 —
   이미 이루어진 일에 대한 길함이면 done입니다.
3. 함께 주는 소상전과 정전 주석을 근거로 삼으십시오. 주석가가 그 형세를
   조건으로 읽었는지, 이미 벌어진 일로 읽었는지가 가장 좋은 단서입니다.
4. 이유는 한 줄로, 원문의 어느 대목 때문인지 밝히십시오.

■ 출력
아래 JSON 객체 하나만. 설명도 코드펜스도 없이 JSON만.

{"id": "<주어진 id 그대로>", "judgment": "changeable | done | unclear", "reason": "<한 줄>"}"""


async def load_context() -> Dict[str, str]:
    """항목마다 소상전과 정전 주석을 모은다."""
    async with AsyncSessionLocal() as s:
        chunks = (await s.execute(select(InterpretationChunk).where(
            InterpretationChunk.source_type.in_(["line_comm", "guasa_comm", "sosang"])
        ))).scalars().all()
    ctx: Dict[str, List[str]] = {}
    for c in chunks:
        key = f"H{c.hexagram_id}" if c.source_type == "guasa_comm" else f"L{c.hexagram_id}-{c.line_number}"
        label = {"sosang": "소상전", "line_comm": "정전 주석", "guasa_comm": "정전 주석"}[c.source_type]
        ctx.setdefault(key, []).append(f"[{label}] {(c.content_ko or '')[:400]}")
    return {k: "\n".join(v[:3]) for k, v in ctx.items()}


def judge(item: Dict[str, Any], ctx: str, tr, retries: int = 3) -> Dict[str, Any]:
    msg = (f"[id] {item['id']}\n"
           f"[괘] 제{item['hexagram_id']}괘 {item['name_hanja']}\n"
           f"[원문] {item['source']}\n"
           f"[번역] {item['translation_ko']}\n"
           f"{ctx}")
    last = None
    for attempt in range(1, retries + 1):
        try:
            rec = tr.translate(msg)
            rec["id"] = item["id"]
            if rec.get("judgment") not in ("changeable", "done", "unclear"):
                raise ValueError(f"알 수 없는 판정: {rec.get('judgment')}")
            return rec
        except Exception as e:                     # noqa: BLE001
            last = e
            print(f"  ⚠️ [{item['id']}] {attempt}/{retries}: {e}")
            if attempt < retries:
                time.sleep(attempt * 2)
    return {"id": item["id"], "judgment": "unclear", "reason": f"ERROR: {last}", "_failed": True}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="data/verdict_modality.json")
    ap.add_argument("-o", "--output", default="data/verdict_modality_judgments.json")
    ap.add_argument("-m", "--model", default=None)
    ap.add_argument("-c", "--concurrency", type=int, default=3)
    ap.add_argument("-l", "--limit", type=int, default=None)
    args = ap.parse_args()

    rows = json.load(open(args.input, encoding="utf-8"))
    todo = [r for r in rows if r["modality"] == "unmarked"]
    if args.limit:
        todo = todo[:args.limit]

    ctx = asyncio.run(load_context())
    model = args.model or settings.CLAUDE_MODEL or os.getenv("CLAUDE_MODEL")
    if not model:
        raise SystemExit("CLAUDE_MODEL이 없다. --model로 줄 것.")
    tr = ClaudeTranslator(model_name=model, system_prompt=SYSTEM)
    print(f"{model} @ {tr.endpoint_desc} | 대상 {len(todo)}건")

    out, lock = {}, threading.RLock()
    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futs = {ex.submit(judge, it, ctx.get(it["id"], ""), tr): it for it in todo}
        for f in as_completed(futs):
            rec = f.result()
            with lock:
                out[rec["id"]] = rec
                Path(args.output).write_text(
                    json.dumps([out[i["id"]] for i in todo if i["id"] in out],
                               ensure_ascii=False, indent=2), encoding="utf-8")

    from collections import Counter
    c = Counter(r["judgment"] for r in out.values())
    print(f"\nchangeable {c['changeable']} / done {c['done']} / unclear {c['unclear']}")
    failed = [r["id"] for r in out.values() if r.get("_failed")]
    if failed:
        print(f"실패 {len(failed)}건: {', '.join(failed)}")
    print(f"→ {args.output}")


if __name__ == "__main__":
    main()
