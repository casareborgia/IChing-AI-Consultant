"""RAG 청크 1,751건을 한국어로 옮긴다 (4단계).

    python scripts/translate_chunks.py -o data/translations/chunks_claude.json -c 2

translate.py의 호출·재시도·이어하기 기계를 그대로 쓰고, 프롬프트와 사용자 메시지만
다르다. 3단계와 조건을 같게 두려는 것이다(temperature 0, 1건 1호출, 상한 8192).

프롬프트는 prompts/rag_translation.md에서 읽는다. 코드에 복사해 두면 원본과
어긋나고, 어긋난 줄 아무도 모른다.
"""
import argparse
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.translate import (  # noqa: E402
    ClaudeTranslator, VertexGeminiTranslator,
    load_existing_results, save_results, settings,
)

PROMPT_MD = PROJECT_ROOT / "prompts" / "rag_translation.md"

# 청크 성격을 사람 말로. 같은 한자라도 무엇에 붙은 글인지에 따라 뜻이 달라진다.
SOURCE_LABEL = {
    "gwa_intro":    "괘 전체를 개관하는 정전 서두 해설 (序卦 풀이)",
    "guasa_comm":   "괘사에 대한 정전 주석",
    "tanjon":       "단전",
    "tanjon_comm":  "단전에 대한 정전 주석",
    "daesang":      "대상전",
    "daesang_comm": "대상전에 대한 정전 주석",
    "line_comm":    "{pos}효 효사에 대한 정전 주석",
    "sosang":       "{pos}효 소상전",
    "sosang_comm":  "{pos}효 소상전에 대한 정전 주석",
}


def fenced(md: str, heading: str) -> str:
    i = md.find(heading)
    if i < 0:
        raise ValueError(f"{PROMPT_MD}에 '{heading}' 절이 없다")
    m = re.search(r"```[^\n]*\n(.*?)```", md[i:], re.DOTALL)
    if not m:
        raise ValueError(f"'{heading}' 절 아래에 코드블록이 없다")
    return m.group(1).rstrip("\n")


def build_prompts(glossary_path: str) -> Dict[str, str]:
    md = PROMPT_MD.read_text(encoding="utf-8")
    system = fenced(md, "## 시스템 프롬프트")
    glossary = Path(glossary_path).read_text(encoding="utf-8").strip()
    if "{GLOSSARY}" not in system:
        raise ValueError("시스템 프롬프트에 {GLOSSARY} 자리가 없다")
    return {"system": system.replace("{GLOSSARY}", glossary),
            "template": fenced(md, "## 사용자 메시지 템플릿")}


def user_message(template: str, chunk: Dict[str, Any], hex_names: Dict[int, str]) -> str:
    pos = chunk.get("line_number") or 0
    label = SOURCE_LABEL[chunk["source_type"]].format(pos=pos)
    hid = chunk["hexagram_id"]
    return template.format(
        id=chunk["id"],
        hexagram=f"제{hid}괘 {hex_names.get(hid, '')}",
        source_label=label,
        content=chunk["content"],
    )


def translate_one(chunk, translator, prompts, hex_names, max_retries) -> Dict[str, Any]:
    cid = str(chunk["id"])
    msg = user_message(prompts["template"], chunk, hex_names)
    last = None
    for attempt in range(1, max_retries + 1):
        t0 = time.time()
        try:
            rec = translator.translate(msg)   # 시스템 프롬프트는 생성 시 넣어 뒀다
            if not isinstance(rec, dict):
                raise ValueError("JSON 객체가 아님")
            rec["id"] = cid
            rec["_meta"] = {
                "model": translator.model_name,
                "endpoint": getattr(translator, "endpoint_desc", "unknown"),
                "elapsed_sec": round(time.time() - t0, 2),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "attempt": attempt,
                "status": "success",
            }
            return rec
        except Exception as e:                      # noqa: BLE001
            last = e
            print(f"  ⚠️ [{cid}] {attempt}/{max_retries} 실패: {type(e).__name__}: {e}")
            if attempt < max_retries:
                time.sleep(attempt * 2)
    return {
        "id": cid, "translation_ko": None, "confidence": "low",
        "flag": f"ERROR: {last}",
        "_meta": {"model": translator.model_name, "status": "failed", "error": str(last),
                  "timestamp": datetime.now(timezone.utc).isoformat()},
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-i", "--input", default="data/rag_chunks.json")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("-p", "--provider", choices=["claude", "gemini"], default="claude")
    ap.add_argument("-m", "--model", default=None)
    ap.add_argument("-c", "--concurrency", type=int, default=1)
    ap.add_argument("-l", "--limit", type=int, default=None)
    ap.add_argument("--glossary", default="pilot/glossary_block.txt")
    ap.add_argument("--retries", type=int, default=3)
    args = ap.parse_args()

    prompts = build_prompts(args.glossary)
    chunks = json.loads(Path(args.input).read_text(encoding="utf-8"))
    if args.limit:
        chunks = chunks[:args.limit]
    hex_names = {h["hexagram_id"]: h["name_hanja"]
                 for h in json.loads((PROJECT_ROOT / "data" / "hexagrams.json").read_text(encoding="utf-8"))}

    if args.provider == "claude":
        model = args.model or settings.CLAUDE_MODEL or os.getenv("CLAUDE_MODEL")
        if not model:
            raise SystemExit("CLAUDE_MODEL이 없다. --model로 주거나 .env에 넣을 것.")
        tr = ClaudeTranslator(model_name=model, project_id=settings.GOOGLE_CLOUD_PROJECT,
                              region=settings.CLAUDE_LOCATION, system_prompt=prompts["system"])
    else:
        tr = VertexGeminiTranslator(model_name=args.model or settings.GEMINI_MODEL,
                                    project_id=settings.GOOGLE_CLOUD_PROJECT,
                                    location=settings.GEMINI_LOCATION,
                                    system_prompt=prompts["system"])
    print(f"{tr.model_name} @ {tr.endpoint_desc} | 용어표 {args.glossary}")

    out = Path(args.output)
    done = load_existing_results(out)
    todo = [c for c in chunks if str(c["id"]) not in done]
    print(f"대상 {len(chunks)}건, 이미 끝난 것 {len(done)}건 → 호출 {len(todo)}건")

    results = dict(done)
    lock = threading.RLock()

    def save():
        save_results(out, [results[str(c["id"])] for c in chunks if str(c["id"]) in results], lock=lock)

    n = 0
    with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as ex:
        futs = {ex.submit(translate_one, c, tr, prompts, hex_names, args.retries): c for c in todo}
        for f in as_completed(futs):
            rec = f.result()
            with lock:
                results[str(rec["id"])] = rec
                n += 1
                if n % 25 == 0 or n == len(todo):
                    print(f"[{n}/{len(todo)}] {rec['id']}")
                save()

    failed = [r["id"] for r in results.values() if r.get("_meta", {}).get("status") == "failed"]
    print(f"\n저장 → {out} ({len(results)}건, 실패 {len(failed)}건)")
    if failed:
        print("실패:", ", ".join(map(str, failed[:20])))
        sys.exit(1)


if __name__ == "__main__":
    main()
