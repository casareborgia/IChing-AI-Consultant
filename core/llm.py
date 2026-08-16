"""LLM 호출 단일화 및 Provider 중립 클라이언트 인터페이스.

- Anthropic Direct API / Vertex AI / Ollama / Gemini 지원
- 역할(role)별 모델 분리
- JSON 정제 및 지수 백오프 자동 재시도 (기본 3회)
"""

import json
import os
import re
import time
from typing import Any, Dict, Optional, Protocol, runtime_checkable
import urllib.request
import urllib.error

from core.config import settings


def clean_json_response(raw_text: str) -> str:
    """마크다운 코드펜스나 주변 텍스트를 제거하고 순수 JSON 문자열만 추출합니다."""
    text = raw_text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        return match.group(1).strip()

    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        return text[first_brace : last_brace + 1].strip()

    return text


@runtime_checkable
class LLMClient(Protocol):
    """LLM 클라이언트 공통 인터페이스 프로토콜."""

    def complete_json(
        self,
        user: str,
        *,
        system: str,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """사용자 입력과 시스템 프롬프트를 받아 JSON Dict 형태로 응답을 반환합니다."""
        ...


class AnthropicClient:
    """Anthropic 직결 API 및 Vertex AI Claude 지원 클라이언트."""

    def __init__(
        self,
        model_name: str,
        project_id: Optional[str] = None,
        region: Optional[str] = None,
        retries: int = 3,
        system_prompt: Optional[str] = None,
        max_tokens: int = 4096,
    ):
        import anthropic

        self.model_name = model_name
        self.retries = retries
        self.system_prompt = system_prompt
        self.max_tokens = max_tokens
        api_key = os.getenv("ANTHROPIC_API_KEY")

        if api_key:
            self.client = anthropic.Anthropic(api_key=api_key)
            self.endpoint_desc = "anthropic:direct_api"
        else:
            proj = project_id or settings.GOOGLE_CLOUD_PROJECT or os.getenv("GOOGLE_CLOUD_PROJECT")
            loc = region or settings.CLAUDE_LOCATION or os.getenv("CLAUDE_LOCATION", "us-east5")
            if not proj:
                raise ValueError("ANTHROPIC_API_KEY 또는 GOOGLE_CLOUD_PROJECT 설정이 필요합니다.")
            self.client = anthropic.AnthropicVertex(
                project_id=proj,
                region=loc,
            )
            self.endpoint_desc = f"vertexai:{loc}"

    def complete_json(
        self,
        user: str,
        *,
        system: str = "",
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        max_tokens = max_tokens or self.max_tokens
        sys_prompt = system or self.system_prompt or ""
        last_err = None
        for attempt in range(1, self.retries + 1):
            try:
                response = self.client.messages.create(
                    model=self.model_name,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=sys_prompt,
                    messages=[{"role": "user", "content": user}],
                )
                raw_text = response.content[0].text if response.content else ""
                cleaned = clean_json_response(raw_text)
                return json.loads(cleaned)
            except Exception as e:
                last_err = e
                if attempt < self.retries:
                    time.sleep(attempt * 1.5)
        raise RuntimeError(f"Anthropic API 호출 실패 ({self.retries}회 재시도 소진): {last_err}") from last_err

    # 레거시 translate 호환용
    def translate(self, prompt: str) -> Dict[str, Any]:
        return self.complete_json(prompt, system=self.system_prompt or "")


class OllamaClient:
    """로컬 Ollama REST API 클라이언트."""

    def __init__(
        self,
        model_name: str,
        base_url: Optional[str] = None,
        retries: int = 3,
        system_prompt: Optional[str] = None,
        max_tokens: int = 4096,
    ):
        self.model_name = model_name
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.retries = retries
        self.system_prompt = system_prompt
        self.max_tokens = max_tokens
        self.endpoint_desc = f"ollama:{self.base_url}"
        # 직전 호출의 시간 분해. 로컬에서 "느리다"는 말은 쓸모가 없다 —
        # 모델 로드인지, 입력 처리인지, 생성인지에 따라 처방이 완전히 달라진다.
        # Ollama가 응답에 담아 보내주는 값을 그냥 버리고 있었다.
        # 순차 호출을 전제로 한다. 동시 호출 시에는 마지막 값만 남는다.
        self.last_timing: Optional[Dict[str, float]] = None

    @staticmethod
    def _timing(body: Dict[str, Any]) -> Dict[str, float]:
        """나노초 단위 필드를 초로 바꾸고 토큰 처리 속도를 계산한다."""
        ns = 1_000_000_000
        load = body.get("load_duration", 0) / ns
        p_dur = body.get("prompt_eval_duration", 0) / ns
        g_dur = body.get("eval_duration", 0) / ns
        p_tok = body.get("prompt_eval_count", 0)
        g_tok = body.get("eval_count", 0)
        return {
            "total": body.get("total_duration", 0) / ns,
            "load": load,
            "prompt_seconds": p_dur,
            "gen_seconds": g_dur,
            "prompt_tokens": p_tok,
            "gen_tokens": g_tok,
            "prompt_tps": (p_tok / p_dur) if p_dur else 0.0,
            "gen_tps": (g_tok / g_dur) if g_dur else 0.0,
        }

    def complete_json(
        self,
        user: str,
        *,
        system: str = "",
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        max_tokens = max_tokens or self.max_tokens
        sys_prompt = system or self.system_prompt or ""
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model_name,
            "prompt": user,
            "system": sys_prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})

        last_err = None
        for attempt in range(1, self.retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=600) as resp:
                    res_body = json.loads(resp.read().decode("utf-8"))
                    self.last_timing = self._timing(res_body)
                    raw_text = res_body.get("response", "")
                    cleaned = clean_json_response(raw_text)
                    return json.loads(cleaned)
            except Exception as e:
                last_err = e
                if attempt < self.retries:
                    time.sleep(attempt * 1.5)
        raise RuntimeError(f"Ollama 호출 실패 ({self.retries}회 재시도 소진): {last_err}") from last_err

    def translate(self, prompt: str) -> Dict[str, Any]:
        return self.complete_json(prompt, system=self.system_prompt or "")


class LMStudioClient:
    """LM Studio의 OpenAI 호환 서버 클라이언트.

    LM Studio가 내려받는 것은 MLX safetensors라 Ollama가 읽지 못한다. 변환하는
    대신 이미 떠 있는 서버에 붙는다 — 파일을 옮기지 않아도 되고, MLX 런타임
    그대로의 속도를 잰다는 이점이 있다.
    """

    def __init__(
        self,
        model_name: str,
        base_url: Optional[str] = None,
        retries: int = 3,
        system_prompt: Optional[str] = None,
        max_tokens: int = 4096,
    ):
        self.model_name = model_name
        self.base_url = (base_url or settings.LMSTUDIO_BASE_URL).rstrip("/")
        self.retries = retries
        self.system_prompt = system_prompt
        self.max_tokens = max_tokens
        self.endpoint_desc = f"lmstudio:{self.base_url}"
        self.last_timing: Optional[Dict[str, float]] = None

    def complete_json(
        self,
        user: str,
        *,
        system: str = "",
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        max_tokens = max_tokens or self.max_tokens
        sys_prompt = system or self.system_prompt or ""
        url = f"{self.base_url}/v1/chat/completions"
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
            # response_format은 넣지 않는다. LM Studio는 'json_schema'나 'text'만
            # 받고 OpenAI의 'json_object'를 거부한다(HTTP 400). 에이전트마다 스키마가
            # 달라 json_schema를 여기서 만들 수도 없다. JSON 추출은 응답을 받은 뒤
            # clean_json_response가 한다 — 다른 provider도 같은 방식이다.
        }
        data = json.dumps(payload).encode("utf-8")

        last_err = None
        for attempt in range(1, self.retries + 1):
            try:
                req = urllib.request.Request(
                    url, data=data, headers={"Content-Type": "application/json"}
                )
                started = time.time()
                with urllib.request.urlopen(req, timeout=600) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                elapsed = time.time() - started

                # OpenAI 호환 응답에는 소요 시간이 없다. 토큰 수만 주므로
                # 벽시계 시간으로 생성 속도를 되짚는다.
                usage = body.get("usage") or {}
                gen_tok = usage.get("completion_tokens", 0)
                self.last_timing = {
                    "total": elapsed,
                    "load": 0.0,
                    "prompt_seconds": 0.0,
                    "gen_seconds": elapsed,
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "gen_tokens": gen_tok,
                    "prompt_tps": 0.0,
                    "gen_tps": (gen_tok / elapsed) if elapsed else 0.0,
                }

                raw_text = body["choices"][0]["message"]["content"] or ""
                return json.loads(clean_json_response(raw_text))
            except Exception as e:
                last_err = e
                if attempt < self.retries:
                    time.sleep(attempt * 1.5)
        raise RuntimeError(f"LM Studio 호출 실패 ({self.retries}회 재시도 소진): {last_err}") from last_err

    def translate(self, prompt: str) -> Dict[str, Any]:
        return self.complete_json(prompt, system=self.system_prompt or "")


class GeminiClient:
    """Vertex AI Gemini 클라이언트 (레거시 번역 및 호환용)."""

    def __init__(
        self,
        model_name: str,
        project_id: Optional[str] = None,
        location: Optional[str] = None,
        retries: int = 3,
        system_prompt: Optional[str] = None,
        max_tokens: int = 8192,
    ):
        from google import genai
        from google.genai import types

        proj = project_id or settings.GOOGLE_CLOUD_PROJECT or os.getenv("GOOGLE_CLOUD_PROJECT")
        loc = location or settings.GEMINI_LOCATION or os.getenv("GEMINI_LOCATION", "us-central1")
        if not proj:
            raise ValueError("GOOGLE_CLOUD_PROJECT가 설정되지 않았습니다.")

        self.client = genai.Client(
            vertexai=True,
            project=proj,
            location=loc,
        )
        self.model_name = model_name
        self.location = loc
        self.retries = retries
        self.system_prompt = system_prompt
        self.max_tokens = max_tokens
        self.endpoint_desc = f"vertexai:{loc}"
        self._types = types

    def complete_json(
        self,
        user: str,
        *,
        system: str = "",
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        max_tokens = max_tokens or self.max_tokens
        sys_prompt = system or self.system_prompt or ""
        config = self._types.GenerateContentConfig(
            temperature=temperature,
            system_instruction=sys_prompt,
            max_output_tokens=max_tokens,
        )
        last_err = None
        for attempt in range(1, self.retries + 1):
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=user,
                    config=config,
                )
                raw_text = response.text or ""
                cleaned = clean_json_response(raw_text)
                return json.loads(cleaned)
            except Exception as e:
                last_err = e
                if attempt < self.retries:
                    time.sleep(attempt * 1.5)
        raise RuntimeError(f"Gemini API 호출 실패 ({self.retries}회 재시도 소진): {last_err}") from last_err

    def translate(self, prompt: str) -> Dict[str, Any]:
        return self.complete_json(prompt, system=self.system_prompt or "")


def get_client(
    role: str = "default",
    provider: Optional[str] = None,
    model: Optional[str] = None,
    system_prompt: Optional[str] = None,
) -> LLMClient:
    """역할(role)과 Provider에 맞는 LLM 클라이언트를 반환합니다.

    role: "safety" | "intake" | "interpret" | "counsel" | "journal" | "default"
    """
    prov = (provider or settings.LLM_PROVIDER or os.getenv("LLM_PROVIDER", "anthropic")).lower()

    # 역할별 지정 모델 조회
    role_models = {
        "safety": settings.SAFETY_MODEL,
        "intake": settings.INTAKE_MODEL,
        "interpret": settings.INTERPRET_MODEL,
        "counsel": settings.COUNSEL_MODEL,
        "journal": settings.JOURNAL_MODEL,
    }
    role_model = role_models.get(role, "")

    if prov == "anthropic":
        model_name = (
            model
            or role_model
            or settings.CLAUDE_MODEL
            or os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")
        )
        return AnthropicClient(model_name=model_name, system_prompt=system_prompt)

    elif prov == "ollama":
        model_name = (
            model
            or role_model
            or settings.OLLAMA_MODEL
            or os.getenv("OLLAMA_MODEL", "gemma2:latest")
        )
        return OllamaClient(model_name=model_name, system_prompt=system_prompt)

    elif prov == "lmstudio":
        model_name = (
            model
            or role_model
            or settings.LMSTUDIO_MODEL
            or os.getenv("LMSTUDIO_MODEL", "google/gemma-4-e4b")
        )
        return LMStudioClient(model_name=model_name, system_prompt=system_prompt)

    elif prov == "gemini":
        model_name = (
            model
            or role_model
            or settings.GEMINI_MODEL
            or os.getenv("GEMINI_MODEL", "gemini-2.5-pro")
        )
        return GeminiClient(model_name=model_name, system_prompt=system_prompt)

    else:
        raise ValueError(f"지원하지 않는 LLM provider입니다: {prov}")
