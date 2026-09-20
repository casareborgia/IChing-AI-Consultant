from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    POSTGRES_USER: str = "iching"
    POSTGRES_PASSWORD: str = "changeme"
    POSTGRES_DB: str = "iching"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    DATABASE_URL: str = "postgresql+asyncpg://iching:changeme@localhost:5432/iching"
    ENVIRONMENT: str = "development"  # "development" | "production"
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173,http://localhost:8765"
    # Vercel 프리뷰 배포처럼 오리진이 매번 바뀌는 경우에만 쓴다. 기본값은 비어 있다 —
    # `^https://.*\.vercel\.app$` 같은 넓은 식은 넣지 말 것. vercel.app 하위 도메인은
    # 누구나 무료로 받으므로 allow_credentials=True 와 만나면 사실상 개방이 된다.
    # 꼭 필요하면 프로젝트 이름까지 박아 좁힌다:
    #   ^https://iching-ai-consultant-[a-z0-9-]+\.vercel\.app$
    CORS_ORIGIN_REGEX: str = ""

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

    # 종료된 상담을 이어갈 때의 세션 전체 턴 상한. 5턴 코칭 아크 뒤의 후속 대화를
    # 포함한 총합이다. 상한이 없으면 한 세션이 무한정 길어져 비용이 선형으로 는다.
    RESUME_MAX_TURNS: int = 15

    # --- Role-specific Models (비어 있으면 기본 CLAUDE_MODEL / OLLAMA_MODEL 사용) ---
    SAFETY_MODEL: str = ""
    INTAKE_MODEL: str = ""
    INTERPRET_MODEL: str = ""
    COUNSEL_MODEL: str = ""
    JOURNAL_MODEL: str = ""

    # --- Authentication (Supabase JWT) ---
    # Supabase 프로젝트 URL (JWKS 공개키 조회용)
    SUPABASE_URL: str = "https://your-project.supabase.co"
    # Supabase 프로젝트의 Legacy JWT Secret (HS256 서명용). Cloud Run에서는 Secret Manager로 주입받는다.
    SUPABASE_JWT_SECRET: str = ""


    # --- Security & Cryptography ---
    # ACT 행동 전념 카드 및 민감 상담 데이터 암호화용 32바이트 키 (미지정 시 안전 파생키 사용)
    ACTION_CARD_ENCRYPTION_KEY: str = ""

    # --- 인증 경계 (T02-BE) ---
    # 개발용 dev-token 우회. 예전에는 `ENVIRONMENT != "production"` 하나로 열렸는데,
    # ENVIRONMENT 기본값이 "development"라 환경변수가 누락된 배포에서 우회가 살아 있었다.
    # 이제는 이 값을 명시적으로 켠 경우에만 열린다(fail-closed).
    DEV_AUTH_BYPASS_ENABLED: bool = False

    # JWKS 조회 타임아웃(초). 지정하지 않으면 라이브러리 기본값 30초가 걸려
    # 키 회전·JWKS 장애 시 요청이 길게 매달린다.
    JWKS_TIMEOUT_SECONDS: float = 3.0

    # 검증된 사용자 기준 분당 요청 한도. 토큰을 갱신해도 초기화되지 않는다.
    # 인스턴스 간 공유 저장소는 T11에서 도입한다. 현재는 프로세스 로컬이다.
    USER_RATE_LIMIT_PER_MINUTE: int = 30

    # --- 출시 단계와 기능 게이트 ---
    # 운영 사실(실제 사업자·계약·리전)과 정책 승인은 코드가 판정할 수 없다. 여기 값들은
    # "무엇을 켜도 되는지"에 대한 운영자의 명시적 표시이며, 기본값은 전부 닫는 쪽이다.
    # 게이트 판정 로직은 core/release_gate.py 참고.
    #
    # SERVICE_STAGE: 무료 베타를 먼저 열고 유료는 추후 도입한다(2026-09-07 결정).
    #   "free_beta"  결제 없음. 상담은 무료 크레딧으로만 소비한다.
    #   "commercial" 유료 판매. D06~D09 승인과 결제 구현이 모두 끝난 뒤에만 쓴다.
    SERVICE_STAGE: str = "free_beta"

    # --- 무료 베타 크레딧 및 12시간 자동 충전 정책 ---
    # 상담 1턴당 차감 크레딧. 무료 베타에서도 0으로 두지 않는다.
    CONSULTATION_CREDIT_COST: int = 10
    # 가입 시 1회 지급 웰컴 크레딧.
    WELCOME_CREDITS: int = 50
    # 무료 베타 자동 충전 목표 잔액. 12시간 경과 시 이 값까지 잔액을 채운다.
    FREE_BETA_REFILL_CREDITS: int = 50
    # 무료 베타 자동 충전 주기(시간). 마지막 충전(또는 웰컴)으로부터 경과해야 하는 시간(12시간).
    FREE_BETA_REFILL_HOURS: int = 12

    # 결제 기능 전체의 마스터 스위치. 무료 베타 동안 True로 바꾸지 않는다.
    PURCHASE_ENABLED: bool = False
    # 결제 연동 경로. 실제 PG는 D09 승인 후에만 지정한다.
    PAYMENT_PROVIDER: str = "mock"
    # 유료 크레딧 소멸 배치. 유료 크레딧의 법적 성격 확인 전까지 켜지 않는다.
    PAID_CREDIT_EXPIRY_ENABLED: bool = False
    # 상담 내용의 품질개선·학습 재사용. 동의 체계와 철회 처리가 갖춰지기 전까지 닫는다.
    QUALITY_REUSE_ENABLED: bool = False

    # 상담 생성(LLM 호출)의 운영자 킬 스위치. 장애·비용 급증 시 즉시 내리는 용도다.
    # 기본값이 True인 것은 현재 서비스가 이미 동작 중이기 때문이다. 배포 때 이 값이
    # 빠졌다는 이유로 정상 서비스가 멈추면 안 된다.
    GENERATION_ENABLED: bool = True

    # 새로 만드는 리포트의 판본. "legacy" | "2.0"
    #
    # **기본값이 legacy인 것은 의도다.** 프런트엔드가 v2 구조를 읽기 전에 v2를
    # 내려보내면 화면이 빈칸이 된다. FE 통합과 브라우저 검증이 끝난 뒤에 운영자가
    # 올린다. 되돌릴 때는 다시 "legacy"로 내리면 되고, **이미 저장된 v2 리포트는
    # 그대로 읽힌다** — 이 값은 생성에만 관여하고 조회에는 관여하지 않는다.
    REPORT_SCHEMA_VERSION: str = "legacy"

    # 런타임 AI 비용 상한 및 예산 쿼터 (A02).
    # 외부 트래픽 유입에 따른 비용 급증 및 금전적 위험을 선제 차단한다.
    LLM_BUDGET_ENABLED: bool = True
    LLM_DAILY_COST_BUDGET_USD: float = 10.0
    LLM_MONTHLY_COST_BUDGET_USD: float = 100.0
    LLM_MAX_INPUT_TOKENS_PER_CALL: int = 16384

    # AI 호출을 허용할 provider와 리전. 키가 존재한다는 이유만으로 다른 경로로
    # 넘어가지 않게 막는다. 쉼표로 구분한다.
    LLM_ALLOWED_PROVIDERS: str = "gemini,ollama,lmstudio,anthropic"
    LLM_ALLOWED_REGIONS: str = "us-central1,us-east5"

    # --- 자체 방문자 통계 (운영 대시보드의 방문자수·재방문 횟수) ---
    #
    # **기본값이 꺼짐인 것은 의도다.** 방문 로그는 개인정보처리방침에 수집 항목으로
    # 고지된 뒤에 켜야 한다. 코드가 배포됐다는 이유로 수집이 시작되면 안 된다.
    VISITOR_ANALYTICS_ENABLED: bool = False
    # 방문자 식별자를 해시할 때 섞는 서버 전용 비밀값. 최소 16자.
    #
    # 이 값이 없거나 너무 짧으면 브라우저가 보낸 식별자를 사실상 그대로 저장하는
    # 꼴이 되므로, ENABLED가 켜져 있어도 수집하지 않는다(fail-closed). 값을 교체하면
    # 기존 행과 새 행의 해시가 달라져 같은 브라우저가 새 방문자로 잡힌다 — 교체는
    # 지표 연속성을 끊는 결정이다.
    VISITOR_ID_PEPPER: str = ""
    # 같은 방문자의 연속 요청을 한 번의 방문으로 묶는 간격(분). 업계 관례인 30분.
    VISIT_SESSION_GAP_MINUTES: int = 30
    # 방문 로그 보존 기간(일). 경과분은 운영 대시보드를 열 때 파기한다.
    VISIT_RETENTION_DAYS: int = 180

    # 운영자 상태 조회(/api/ops/*) 권한을 가진 Supabase user_id 목록 (쉼표 구분).
    OPERATOR_USER_IDS: str = ""
    # 운영자 이메일 목록 (쉼표 구분). 기본 운영자 casareborgia@gmail.com 포함 가능.
    OPERATOR_EMAILS: str = ""

    # 운영자가 확인을 마친 결정 ID 목록(D01~D13). 쉼표로 구분한다.
    # 코딩 에이전트가 이 값을 채우지 않는다. 운영자만 기입한다.
    #
    # 주의: 이 값만으로는 게이트가 열리지 않는다. D 번호는 "무엇을 검토했는가"의
    # 목록일 뿐 검토 결과물이 실재한다는 증거가 아니다. 아래 증거 설정이 함께
    # 필요하다(core/release_gate.py의 check_free_beta_evidence 참고).
    OPERATOR_ATTESTED_DECISIONS: str = ""

    # --- 무료 베타 공개 증거 (CYCLE-01-R3) ---
    # 기계가 확인할 수 있는 최소 증거만 모델링한다. 값의 진위는 확인하지 못하며
    # 형식과 미기입 여부만 검사한다. 기본값은 전부 비어 있어 fail-closed다.

    # 게시된 정책 문서 묶음의 버전. 날짜 기반 형식을 요구한다. 예: 2026-09-08 또는 2026-09-08.2
    LEGAL_DOCUMENTS_VERSION: str = ""
    # 정책 문서가 초안이 아니라 실제 게시 상태인지.
    LEGAL_DOCUMENTS_PUBLISHED: bool = False

    # 무료 베타 공개를 승인한 운영자와 승인일(YYYY-MM-DD).
    FREE_BETA_LAUNCH_APPROVED_BY: str = ""
    FREE_BETA_LAUNCH_APPROVED_AT: str = ""

    # 인수기준 검증을 통과한 코드 커밋의 40자리 SHA와 그때 사용한 검사 묶음 버전.
    # 이 두 값은 "기대값"이며 그 자체가 증거는 아니다. 아래 서명된 manifest가
    # 같은 값을 담고 있어야 검증이 통과한다(core/release_evidence.py).
    ACCEPTANCE_EVIDENCE_SHA: str = ""
    ACCEPTANCE_EVIDENCE_SUITE_VERSION: str = ""

    # CI가 서명한 인수증거 manifest 파일 경로.
    ACCEPTANCE_MANIFEST_PATH: str = ""
    # DEPRECATED / no-op. 아무 것도 읽지 않는다.
    #
    # 예전에는 이 값이 manifest 서명을 검증할 공개키였다. 그러면 배포 환경변수를
    # 바꿀 수 있는 사람이 자기 키를 넣고 자기가 서명한 manifest를 함께 넣어,
    # 테스트를 한 번도 돌리지 않은 커밋을 "인수기준 통과"로 만들 수 있었다.
    # 서명하는 쪽과 검증하는 쪽이 같아지면 서명은 아무 것도 증명하지 못한다.
    #
    # 이제 신뢰 anchor는 `core/release_trust.py`에 코드로 박혀 있고, 코드 리뷰를
    # 거친 빌드 입력으로만 바뀐다. 이 설정을 어떤 값으로 채우든 검증 결과는
    # 달라지지 않는다. 기존 배포의 .env가 이 이름을 갖고 있어도 기동이 깨지지
    # 않도록 필드만 남겨 둔다.
    ACCEPTANCE_EVIDENCE_PUBLIC_KEY: str = ""
    # 빌드된 이미지가 어느 커밋에서 나왔는지. 빌드 시 주입한다.
    # manifest의 target_sha와 일치해야 증거가 이 빌드에 묶인다.
    BUILD_GIT_SHA: str = ""

    # --- 로깅 ---
    # uvicorn은 자기 로거만 설정하고 root는 건드리지 않는다. 앱에서 별도로 잡아주지
    # 않으면 root에 핸들러가 없어 기본 레벨 WARNING이 걸리고, logger.info()가 통째로
    # 사라진다. 실제로 리포트 생성의 status/duration_ms 로그가 운영에서 한 줄도
    LOG_LEVEL: str = "INFO"

    # Cloud Run 및 프록시 헤더 신뢰 설정 (X-Forwarded-For)
    # 프로덕션에서는 미설정 시 기동 실패(fail-closed)하며 '*'를 허용하지 않는다 (P0/R3).
    # 비운영 환경에서는 '127.0.0.1,::1,169.254.0.0/16' 기본값이 적용된다.
    FORWARDED_ALLOW_IPS: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    from pydantic import model_validator

    @model_validator(mode="after")
    def validate_production_ip_trust(self) -> "Settings":
        raw = (self.FORWARDED_ALLOW_IPS or "").strip()
        if self.ENVIRONMENT == "production":
            if not raw:
                raise ValueError(
                    "프로덕션 환경에서는 FORWARDED_ALLOW_IPS가 반드시 명시적으로 설정되어야 합니다 (fail-closed)."
                )
            if "*" in [item.strip() for item in raw.split(",")]:
                raise ValueError(
                    "프로덕션 환경에서는 FORWARDED_ALLOW_IPS에 '*'를 사용할 수 없으며 "
                    "검증된 프록시 대역(예: Cloud Run GFE 169.254.0.0/16 등)을 명시해야 합니다."
                )
        else:
            if not raw:
                self.FORWARDED_ALLOW_IPS = "127.0.0.1,::1,169.254.0.0/16"
        return self



settings = Settings()


def get_settings() -> Settings:
    return settings

