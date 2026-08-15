"""괘사·효사 한글 번역 배치 생성 스크립트.

지시서(pilot/HANDOFF.md, pilot/PROMPT.md) 및 리팩토링 요건을 준수합니다.
1. 모델 ID·엔드포인트·소요시간 메타데이터를 각 레코드에 기록
2. Gemini/Claude 공통 조건: response_mime_type 미사용, 출력 상한 8192 통일
3. Claude 모델명 임의 기본값 제거 (미지정 시 명시적 오류 발생)
4. 개별 실패 시 전체 중단 대신 실패 기록 후 계속 진행 (내결함성)
5. 멀티스레드 병렬 처리 지원 (--concurrency, 기본 1)
6. 1건 1호출 (Stateless), temperature=0.0, 체크포인트 및 이어하기 보장
"""

import argparse
import hashlib
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
from dotenv import load_dotenv

# 프로젝트 루트를 sys.path에 추가하여 core 모듈 임포트 가능하도록 설정
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.config import settings

load_dotenv()

# 출력 토큰 상한. 두 모델에 같은 값을 쓴다 — 한쪽만 조이면 그 차이가 모델 차이로 오해된다.
#
# 2048로는 안 된다. Gemini 2.5 Pro는 사고(thinking) 토큰이 이 예산에서 함께 빠지고,
# 실측으로 건당 사고가 2,000~3,100토큰이다. 2048에서는 사고만으로 예산이 소진돼
# finishReason=MAX_TOKENS로 잘린 JSON이 나온다(H29 실측: 사고 1963 + 답변 81, 파싱 실패).
# 12건 중 가장 짧은 H1만 통과하므로 1건 테스트로는 이 문제가 드러나지 않는다.
# Claude는 사고를 쓰지 않아 이 값이 커도 손해가 없다 — 상한일 뿐이고 답변은 300자 안쪽이다.
MAX_OUTPUT_TOKENS = 8192

SYSTEM_PROMPT = """당신은 표점(標點)만 찍힌 주역 한문 원문을 현대 한국어로 옮기는 번역자입니다.

원문에는 토(吐)가 달려 있지 않습니다. `初九 磐桓。利居貞。利建侯。`처럼 한문과
구두점뿐이므로, 우리말 어미와 문장 구조를 스스로 세워야 합니다.

■ 이 번역의 용도
이 결과물은 사용자에게 그대로 보여주는 글이 아닙니다. 데이터베이스에 저장되어
뒤이은 해석 단계가 참조하는 '근거 자료'입니다. 따라서 매끄러움보다 정확성이
우선입니다. 상담체·조언체로 각색하지 마십시오. 그 작업은 다음 단계에서 합니다.

■ 반드시 지킬 것
1. 원문에 없는 내용을 더하지 마십시오. 해설, 조언, 위로, 적용 예시 모두 금지입니다.
   "~해야 합니다", "~를 의미하니 조심하세요" 같은 문장은 번역이 아닙니다.
2. 원문에 결손·오탈·이상이 있으면 짐작으로 메우지 말고 flag에 적으십시오.
   그럴듯하게 메운 번역보다, 이상하다고 표시한 번역이 낫습니다.
3. 아래 용어표를 지키십시오. 표에 없는 핵심어를 새로 정했다면 key_terms에 적으십시오.
   386건 전체에서 같은 한자는 같은 우리말로 옮겨야 합니다.
4. 함께 주어지는 정전(程傳) 주석은 뜻을 확정하기 위한 참고자료입니다.
   번역 대상이 아닙니다. 주석 내용을 번역문에 섞지 마십시오.
5. 한자 독음이 통상과 다른 경우(가차·이체·통가자) reading_notes에 근거를 한 줄로 적으십시오.
6. **translation_ko와 xiang_ko에 한자를 남기지 마십시오.** 전부 우리말로 옮깁니다.
   - 효 이름: 初九 → 초구, 六二 → 육이, 上九 → 상구, 用九 → 용구
   - 괘 이름: 屯 → 준, 蠱 → 고, 无妄 → 무망 (독음으로 적습니다)
   - 뜻을 세우기 어려운 글자라도 음차해 두지 말고 우리말로 풀어 옮기십시오.
     `班如하고` `漣如하다` 같은 표기는 번역이 아닙니다.
   - 한자 병기가 꼭 필요하면 우리말 뒤 괄호에만 넣습니다: 준(屯).
   - 확신이 서지 않으면 임의로 메우지 말고 flag에 적으십시오(2항과 같습니다).

■ 용어표 (고정)
元 으뜸    亨 형통함   利 이로움   貞 곧고 바름
吉 길함    凶 흉함     咎 허물     无咎 허물이 없음
吝 부끄러움  悔 뉘우침   厲 위태로움  孚 미더움
中 치우치지 않음        正 바름     利貞 곧게 지키면 이롭다

■ 출력
아래 JSON 객체 하나만 출력하십시오. 설명, 인사말, 코드펜스 없이 JSON만.

{
  "id": "<주어진 id 그대로>",
  "translation_ko": "<원문 번역>",
  "xiang_ko": "<소상전 번역. 소상전이 없으면 null>",
  "key_terms": { "<한자>": "<채택한 우리말>" },
  "reading_notes": "<독음·고유명사·구문 판단 근거. 없으면 빈 문자열>",
  "confidence": "high | medium | low",
  "flag": "<원문 이상이나 판단 불가 지점. 없으면 null>"
}"""


def build_system_prompt(glossary_path: Optional[str]) -> Dict[str, Any]:
    """확정 용어표를 시스템 프롬프트의 '■ 용어표' 자리에 끼워 넣는다.

    새 절을 덧붙이지 않고 원래 자리를 채우는 이유는, 파일럿과 프롬프트 구조를
    같게 두기 위해서다. 표만 15항목에서 확정본으로 넓어진다(HANDOFF C-2).
    돌린 표가 무엇이었는지 나중에 대조할 수 있도록 해시를 함께 돌려준다.
    """
    if not glossary_path:
        return {"prompt": SYSTEM_PROMPT, "glossary": None}

    block = Path(glossary_path).read_text(encoding="utf-8").strip()
    head, sep, rest = SYSTEM_PROMPT.partition("■ 용어표 (고정)\n")
    if not sep:
        raise ValueError("시스템 프롬프트에서 '■ 용어표 (고정)' 절을 찾지 못했다")
    _old_table, out_sep, tail = rest.partition("\n■ 출력")
    prompt = head + sep + block + out_sep + tail
    return {
        "prompt": prompt,
        "glossary": {
            "path": glossary_path,
            "terms": len([l for l in block.splitlines() if l.strip()]),
            "sha256": hashlib.sha256(block.encode("utf-8")).hexdigest()[:12],
        },
    }


def build_user_prompt(item: Dict[str, Any]) -> str:
    """pilot/PROMPT.md 규격에 맞게 사용자 메시지를 조립합니다."""
    lines = [
        f"[id] {item['id']}",
        f"[출처] {item['hexagram']} / {item['target']}",
        f"[원문] {item['source']}",
    ]
    if item.get("xiang"):
        lines.append(f"[소상전] {item['xiang']}")
    if item.get("commentary"):
        lines.append(f"[정전 주석 — 참고용] {item['commentary']}")
    return "\n".join(lines)


def clean_json_response(raw_text: str) -> str:
    """마크다운 코드펜스나 주변 텍스트를 제거하고 순수 JSON 문자열만 추출합니다."""
    text = raw_text.strip()
    # ```json ... ``` 또는 ``` ... ``` 마크다운 블록 추출
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        return match.group(1).strip()
    
    # 첫 { 부터 마지막 } 까지 추출
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        return text[first_brace : last_brace + 1].strip()

    return text


class VertexGeminiTranslator:
    def __init__(self, model_name: str, project_id: str, location: str, system_prompt: str = SYSTEM_PROMPT):
        from google import genai
        from google.genai import types

        self.client = genai.Client(
            vertexai=True,
            project=project_id,
            location=location,
        )
        self.model_name = model_name
        self.project_id = project_id
        self.location = location
        self.endpoint_desc = f"vertexai:{location}"
        self.config = types.GenerateContentConfig(
            temperature=0.0,
            system_instruction=system_prompt,
            max_output_tokens=MAX_OUTPUT_TOKENS,
        )

    def translate(self, prompt: str) -> Dict[str, Any]:
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=self.config,
        )
        raw_text = response.text or ""
        cleaned = clean_json_response(raw_text)
        return json.loads(cleaned)


class ClaudeTranslator:
    def __init__(self, model_name: str, project_id: Optional[str] = None, region: Optional[str] = None,
                 system_prompt: str = SYSTEM_PROMPT):
        import anthropic

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if api_key:
            self.client = anthropic.Anthropic(api_key=api_key)
            self.endpoint_desc = "anthropic:direct_api"
        else:
            if not project_id or not region:
                raise ValueError("Anthropic Direct API Key 또는 Vertex AI 프로젝트/리전 설정이 필요합니다.")
            self.client = anthropic.AnthropicVertex(
                project_id=project_id,
                region=region,
            )
            self.endpoint_desc = f"vertexai:{region}"

        self.model_name = model_name
        self.system_prompt = system_prompt

    def translate(self, prompt: str) -> Dict[str, Any]:
        response = self.client.messages.create(
            model=self.model_name,
            max_tokens=MAX_OUTPUT_TOKENS,
            temperature=0.0,
            system=self.system_prompt,
            messages=[{"role": "user", "content": prompt}],
        )
        raw_text = response.content[0].text if response.content else ""
        cleaned = clean_json_response(raw_text)
        return json.loads(cleaned)


def get_translator(provider: str, model: Optional[str] = None, system_prompt: str = SYSTEM_PROMPT):
    project_id = settings.GOOGLE_CLOUD_PROJECT or os.getenv("GOOGLE_CLOUD_PROJECT")

    if provider == "gemini":
        if not project_id:
            raise ValueError("GOOGLE_CLOUD_PROJECT가 설정되지 않았습니다.")
        model_name = model or settings.GEMINI_MODEL or os.getenv("GEMINI_MODEL", "gemini-2.5-pro")
        location = settings.GEMINI_LOCATION or os.getenv("GEMINI_LOCATION", "us-central1")
        print(f"[설정] Provider: Gemini (Vertex AI) | Model: {model_name} | Location: {location} | Project: {project_id}")
        return VertexGeminiTranslator(model_name=model_name, project_id=project_id, location=location,
                                     system_prompt=system_prompt)

    elif provider == "claude":
        model_name = model or settings.CLAUDE_MODEL or os.getenv("CLAUDE_MODEL")
        if not model_name:
            raise ValueError(
                "Claude 모델명이 설정되지 않았습니다. .env의 CLAUDE_MODEL 또는 --model 인자로 명시해 주십시오."
            )
        location = settings.CLAUDE_LOCATION or os.getenv("CLAUDE_LOCATION", "us-east5")
        t = ClaudeTranslator(model_name=model_name, project_id=project_id, region=location,
                             system_prompt=system_prompt)
        print(f"[설정] Provider: Claude ({t.endpoint_desc}) | Model: {model_name} | Region: {location} | Project: {project_id}")
        return t

    else:
        raise ValueError(f"지원하지 않는 provider입니다: {provider}")


def load_existing_results(output_path: Path) -> Dict[str, Dict[str, Any]]:
    if not output_path.exists():
        return {}
    try:
        data = json.loads(output_path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "results" in data:
            data = data["results"]
        if isinstance(data, list):
            # 실패로 남은 건은 '완료'로 치지 않는다. 그렇지 않으면 이어 돌려도
            # 실패분을 건너뛰어, 450건 중 한 번 실패한 항목은 영영 비어 있게 된다.
            return {
                str(item["id"]): item
                for item in data
                if "id" in item and item.get("_meta", {}).get("status") != "failed"
            }
    except Exception as e:
        print(f"기존 결과 파일 로드 중 경고: {e}")
    return {}


def save_results(output_path: Path, results: List[Dict[str, Any]], lock: Optional[threading.Lock] = None) -> None:
    def _write():
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = output_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(output_path)

    if lock:
        with lock:
            _write()
    else:
        _write()


def process_single_item(
    item: Dict[str, Any],
    translator: Any,
    provider: str,
    max_retries: int = 3,
) -> Dict[str, Any]:
    item_id = str(item["id"])
    user_prompt = build_user_prompt(item)
    last_err: Optional[Exception] = None

    for attempt in range(1, max_retries + 1):
        t0 = time.time()
        try:
            res = translator.translate(user_prompt)
            elapsed = time.time() - t0
            
            # 구조 보장
            res["id"] = item_id
            res["_meta"] = {
                "provider": provider,
                "model": translator.model_name,
                "endpoint": getattr(translator, "endpoint_desc", "unknown"),
                "elapsed_sec": round(elapsed, 2),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "attempt": attempt,
                "status": "success",
                "glossary": getattr(translator, "glossary_meta", None),
            }
            return res
        except Exception as e:
            last_err = e
            wait_sec = attempt * 2
            print(f"  ⚠️ [ID {item_id}] 시도 {attempt}/{max_retries} 실패: {e}. {wait_sec}초 후 재시도...")
            time.sleep(wait_sec)

    # 모든 재시도 실패 시 fallback 레코드 반환 (전체 중단 방지)
    print(f"  ❌ [ID {item_id}] 최종 실패 (계속 진행): {last_err}")
    return {
        "id": item_id,
        "translation_ko": None,
        "xiang_ko": None,
        "key_terms": {},
        "reading_notes": "",
        "confidence": "low",
        "flag": f"ERROR: {str(last_err)}",
        "_meta": {
            "provider": provider,
            "model": translator.model_name,
            "endpoint": getattr(translator, "endpoint_desc", "unknown"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "attempts": max_retries,
            "status": "failed",
            "error": str(last_err),
        },
    }


def run_batch(
    input_file: Path,
    output_file: Path,
    provider: str,
    model: Optional[str] = None,
    limit: Optional[int] = None,
    concurrency: int = 1,
    delay: float = 0.2,
    max_retries: int = 3,
    glossary: Optional[str] = None,
) -> None:
    items: List[Dict[str, Any]] = json.loads(input_file.read_text(encoding="utf-8"))
    if limit:
        items = items[:limit]

    print(f"\n========================================================")
    print(f"주역 괘사·효사 번역 배치 시작")
    print(f"입력: {input_file} (총 {len(items)}건)")
    print(f"출력: {output_file}")
    print(f"동시 실행 수(Concurrency): {concurrency}")
    print(f"========================================================\n")

    sp = build_system_prompt(glossary)
    if sp["glossary"]:
        g = sp["glossary"]
        print(f"용어표: {g['path']} ({g['terms']}항목, sha {g['sha256']})")
    translator = get_translator(provider, model, system_prompt=sp["prompt"])
    translator.glossary_meta = sp["glossary"]
    existing = load_existing_results(output_file)
    print(f"기존 저장된 완료 건수: {len(existing)}건")

    results_map: Dict[str, Dict[str, Any]] = dict(existing)
    items_to_process = [it for it in items if str(it["id"]) not in results_map]
    print(f"새로 처리할 대상 건수: {len(items_to_process)}건\n")

    # RLock이어야 한다. 병렬 경로에서는 락을 쥔 채로 _sync_save()를 부르고,
    # 그 안의 save_results가 같은 락을 한 번 더 잡는다. 재진입이 안 되는
    # threading.Lock을 쓰면 첫 항목이 끝나는 순간 영구 대기에 빠진다.
    file_lock = threading.RLock()

    def _sync_save():
        ordered = [results_map[str(it["id"])] for it in items if str(it["id"]) in results_map]
        save_results(output_file, ordered, lock=file_lock)

    if concurrency <= 1:
        # 순차 실행
        for idx, item in enumerate(items_to_process, 1):
            iid = str(item["id"])
            print(f"[{idx}/{len(items_to_process)}] ID {iid} 처리 중... ({item.get('hexagram')} {item.get('target')})")
            res = process_single_item(item, translator, provider, max_retries)
            results_map[iid] = res
            _sync_save()
            if delay > 0:
                time.sleep(delay)
    else:
        # 멀티스레드 병렬 실행
        completed_count = 0
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            future_to_item = {
                executor.submit(process_single_item, item, translator, provider, max_retries): item
                for item in items_to_process
            }
            for future in as_completed(future_to_item):
                item = future_to_item[future]
                iid = str(item["id"])
                res = future.result()
                with file_lock:
                    results_map[iid] = res
                    completed_count += 1
                    print(f"[{completed_count}/{len(items_to_process)}] ID {iid} 완료 ({res['_meta']['status']}, {res['_meta'].get('elapsed_sec', 0)}s)")
                    _sync_save()
                if delay > 0:
                    time.sleep(delay)

    success_count = sum(1 for r in results_map.values() if r.get("_meta", {}).get("status") == "success")
    fail_count = len(results_map) - success_count

    print(f"\n========================================================")
    print(f"✨ 번역 배치 작업 완료!")
    print(f"총 처리: {len(results_map)}건 (성공: {success_count}건, 실패: {fail_count}건)")
    print(f"저장 경로: {output_file}")
    print(f"========================================================\n")


def main():
    parser = argparse.ArgumentParser(description="주역 괘사·효사 한글 번역 배치 스크립트")
    parser.add_argument("-i", "--input", default="pilot/items.json", help="입력 JSON 파일 경로")
    parser.add_argument("-o", "--output", required=True, help="출력 JSON 파일 경로 (예: pilot/runs/gemini-1.json)")
    parser.add_argument("-p", "--provider", choices=["gemini", "claude"], default="gemini", help="LLM 공급자")
    parser.add_argument("-m", "--model", default=None, help="모델명 (미지정시 .env / settings 기본값 사용)")
    parser.add_argument("-l", "--limit", type=int, default=None, help="실행 항목 수 제한")
    parser.add_argument("-c", "--concurrency", type=int, default=1, help="동시 실행 워커 수 (기본: 1)")
    parser.add_argument("-d", "--delay", type=float, default=0.1, help="호출 간 딜레이(초)")
    parser.add_argument("--glossary", default=None, help="확정 용어표 파일 (프롬프트의 용어표 자리에 들어간다)")
    parser.add_argument("--retries", type=int, default=3, help="실패 시 재시도 횟수")

    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"오류: 입력 파일을 찾을 수 없습니다: {input_path}")
        sys.exit(1)

    run_batch(
        input_file=input_path,
        output_file=output_path,
        provider=args.provider,
        model=args.model,
        limit=args.limit,
        concurrency=args.concurrency,
        delay=args.delay,
        max_retries=args.retries,
        glossary=args.glossary,
    )


if __name__ == "__main__":
    main()
