from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    POSTGRES_USER: str = "iching"
    POSTGRES_PASSWORD: str = "changeme"
    POSTGRES_DB: str = "iching"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    DATABASE_URL: str = "postgresql+asyncpg://iching:changeme@localhost:5432/iching"

    # --- Vertex AI (3단계 번역) ---
    # 리전을 모델별로 나눠 둔 것은 취향이 아니다. Claude는 Vertex 서빙 리전이
    # 한정되어 있어 Gemini와 같은 리전을 쓰지 못할 수 있다. 하나로 합치지 말 것.
    GOOGLE_CLOUD_PROJECT: str = ""
    GEMINI_LOCATION: str = "us-central1"
    GEMINI_MODEL: str = "gemini-2.5-pro"
    CLAUDE_LOCATION: str = "us-east5"
    CLAUDE_MODEL: str = ""  # Model Garden 승인 후 실제 ID로 채운다

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
