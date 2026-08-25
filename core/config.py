from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    POSTGRES_USER: str = "iching"
    POSTGRES_PASSWORD: str = "changeme"
    POSTGRES_DB: str = "iching"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    DATABASE_URL: str = "postgresql+asyncpg://iching:changeme@localhost:5432/iching"

    # --- LLM Providers & Models ---
    # 시험은 로컬, 서비스는 상용 API다(CLAUDE.md 모델 운영 절).
    # 개발 환경에서는 .env에 LLM_PROVIDER=ollama를 둔다.
    LLM_PROVIDER: str = "anthropic"  # "anthropic" | "ollama" | "lmstudio" | "gemini"

    OLLAMA_BASE_URL: str = "http://localhost:11434"
    # 2026-08-16 실측으로 고른 개발용 모델. 형식 72/72, 제약 34/35, 상담 1턴 약 8초.
    # 26B는 이 기기에서 JSON이 잘려 탈락했다. `ollama list`의 이름과 정확히 맞아야 한다.
    OLLAMA_MODEL: str = "gemma4:latest"

    # LM Studio. 같은 모델이라도 런타임이 다르다 — Apple Silicon에서는 MLX가
    # GGUF보다 빠른 것이 보통이라, 모델뿐 아니라 런타임도 후보로 놓고 재야 한다.
    LMSTUDIO_BASE_URL: str = "http://localhost:1234"
    LMSTUDIO_MODEL: str = "google/gemma-4-e4b"

    # --- Vertex AI (3단계 번역 및 레거시) ---
    # 리전을 모델별로 나눠 둔 것은 취향이 아니다. Claude는 Vertex 서빙 리전이
    # 한정되어 있어 Gemini와 같은 리전을 쓰지 못할 수 있다. 하나로 합치지 말 것.
    GOOGLE_CLOUD_PROJECT: str = ""
    GEMINI_LOCATION: str = "us-central1"
    GEMINI_API_KEY: str = ""
    # 서비스 기본값은 Flash 계열이다. Pro는 건당 사고 토큰을 2,000~3,100개 쓰는 것이
    # 3단계에서 실측됐고(scripts/translate.py 참고), 세션당 8호출이면 사고만 2만
    # 토큰이라 출력 과금이 통째로 달라진다. Pro로 올리려면 그 값을 먼저 재볼 것.
    # 실제 모델 ID는 배포 전에 Vertex 콘솔 또는 Gemini API에서 확인해 고정한다.
    GEMINI_MODEL: str = "gemini-2.5-flash"
    CLAUDE_LOCATION: str = "us-east5"
    CLAUDE_MODEL: str = ""  # e.g., claude-sonnet-4-5-20250929 (직결) / claude-sonnet-4-5@20250929 (Vertex)

    # --- 안전 ---
    # 위기 판정이 난 뒤 이 시간 동안은 같은 사용자에게 괘를 뽑지 않는다.
    # 세션이 닫혔다고 위험이 끝난 것은 아니고, 위기 직후의 급격한 평온과 화제
    # 전환은 그 자체가 위험 신호다(prompts/safety_screening.md 판정 규칙 8).
    # 0으로 두면 세션 단위 래치만 걸린다.
    CRISIS_LATCH_HOURS: int = 24

    # --- Role-specific Models (비어 있으면 기본 CLAUDE_MODEL / OLLAMA_MODEL 사용) ---
    SAFETY_MODEL: str = ""
    INTAKE_MODEL: str = ""
    INTERPRET_MODEL: str = ""
    COUNSEL_MODEL: str = ""
    JOURNAL_MODEL: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()

