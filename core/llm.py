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
                with urllib.request.urlopen(req, timeout=120) as resp:
                    res_body = json.loads(resp.read().decode("utf-8"))
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
