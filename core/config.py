from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    POSTGRES_USER: str = "iching"
    POSTGRES_PASSWORD: str = "changeme"
    POSTGRES_DB: str = "iching"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    DATABASE_URL: str = "postgresql+asyncpg://iching:changeme@localhost:5432/iching"

    # --- LLM Providers & Models ---
    LLM_PROVIDER: str = "anthropic"  # "anthropic" | "ollama" | "gemini"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "gemma4:26b"  # 서비스 후보 모델. `ollama list`의 이름과 맞아야 한다

    # --- Vertex AI (3단계 번역 및 레거시) ---
    # 리전을 모델별로 나눠 둔 것은 취향이 아니다. Claude는 Vertex 서빙 리전이
    # 한정되어 있어 Gemini와 같은 리전을 쓰지 못할 수 있다. 하나로 합치지 말 것.
    GOOGLE_CLOUD_PROJECT: str = ""
    GEMINI_LOCATION: str = "us-central1"
    GEMINI_MODEL: str = "gemini-2.5-pro"
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

