# 주역 심층 AI 상담 (I-Ching AI Consultant)

> 주역 64괘와 송대 주석(이천역전·주역본의)에 기반하여, 단순한 점괘가 아닌 **삶의 변화를 읽고 성찰하는 심층 멀티턴 대화형 의사결정 상담 AI**

[![Architecture](https://img.shields.io/badge/Architecture-3--Tier_Serverless-blue?style=flat&logo=googlecloud)](https://github.com/casareborgia/IChing-AI-Consultant)
[![Frontend](https://img.shields.io/badge/Frontend-Next.js_16-black?style=flat&logo=nextdotjs)](https://github.com/casareborgia/IChing-AI-Consultant)
[![Backend](https://img.shields.io/badge/Backend-FastAPI_v1.0-009688?style=flat&logo=fastapi)](https://github.com/casareborgia/IChing-AI-Consultant)
[![Tests](https://img.shields.io/badge/Tests-150_Passed-brightgreen?style=flat&logo=pytest)](https://github.com/casareborgia/IChing-AI-Consultant)
[![Socratic Counsel](https://img.shields.io/badge/Socratic_Counsel-v0.5.0_5Turn_ActionCard-gold?style=flat&logo=openai)](https://github.com/casareborgia/IChing-AI-Consultant)
[![Security](https://img.shields.io/badge/Security-Zero_Trust_JWT-emerald?style=flat&logo=auth0)](https://github.com/casareborgia/IChing-AI-Consultant)
[![License: Code](https://img.shields.io/badge/Code-MIT_License-blue?style=flat)](LICENSE)
[![License: Data](https://img.shields.io/badge/Data-CC_BY--SA_4.0-lightgrey?style=flat)](data/PROVENANCE.md)

---

## 🌟 프로젝트 개요

**I-Ching AI Consultant**는 사용자의 고민을 경청하고, 주자 변효 규칙 엔진을 통해 괘를 도출한 뒤, 전통 원문(괘사·효사)과 송대 주석(정전·본의 2,536건)을 현대적 심리 상담 언어로 풀어내는 AI 상담 시스템입니다.

- **포지셔닝**: 미래를 단정 짓는 '예언자'가 아닌, 스스로 내면의 답을 찾도록 돕는 **'의사결정 지원 동반자이자 거울'**
- **5턴 소크라테스 코칭 대화 엔진 (v0.5.0 NEW)**: 성리학의 자성(自省)과 퇴계의 경(敬) 철학에 기반한 5단계 소크라테스 코칭 모델 도입. 무한 꼬리물기 대화를 방지하는 5턴 하드 가드레일(`is_final: true`) 및 4 Quality Gates 자아비판(Critique & Refinement) 루프를 통해 상투어/클리셰를 배제하고 높은 품격의 한국어 상담을 제공합니다.
- **성찰 결과 액션 카드 v2 및 카드 캔버스 렌더러 (v0.5.0 NEW)**: 5턴 상담 완료 시 내담자의 1가지 구체적 실천 다짐(Action Pledge)을 구조화하여, 모바일/웹 저장 및 공유가 가능한 그래픽 액션 카드로 렌더링하고 안전 암호화 내보내기를 지원합니다.
- **수석 주역 AI 1:1 맞춤 컨설팅 리포트 결합**: TCREI 프레임워크 기반 전용 `Report Agent`가 6효 수리 산출, 주자 고변점 룰, DB 효사 한문 원문, RAG 고전 주석을 종합 융합하여 **4단계 고품격 1:1 맞춤 리포트**를 집필하며, 확정된 리포트 핵심 결론을 `Counsel Agent` 상담 대화 맥락에 1:1 바인딩합니다.
- **근거 투명성 (Provenance)**: AI 환각(Hallucination) 없이 DB 1:1 확정 원문과 pgvector RAG 주석을 프론트엔드 근거 패널에 투명하게 공개
- **다계층 안전망 & SaMD 웰니스**: 위기 신호(자살/자해, 폭력) 감지 시 괘 도출을 차단하고 24시간 자살예방 상담전화(`109`)로 즉시 안전 이관 (24시간 위기 래치 적용 및 100% 자동 크레딧 환불)
- **제로 트러스트 보안 (Zero-Trust)**: 요청 본문 `user_id`를 불허하고, Supabase JWT 서명 검증(`HS256`, `audience="authenticated"`)을 통해 신원을 강제 확정하여 위기 래치 및 세션 소유권(BOLA) 변조를 원천 차단

---

## 📋 4단계 고품격 주역 컨설팅 리포트 구조 (v0.3.0)

> 백엔드 LLM(Gemini)이 내담자 사연에 맞게 100% 가변형으로 직접 집필하는 1:1 심층 성찰 보고서 서식입니다.

```markdown
1. 질문 및 마음가짐 세팅 (사례 설정)
   - 질문자의 고민 사연 100% 반영
   - 재삼덕 금기 점서 예식 명시 (사리사욕을 비운 경건한 단 1회 점서 원칙)

2. 괘 도출 과정 (수리 도출 및 효 쌓기)
   - 1효(초효) ~ 6효(상효) 수리 산출 (소양 7, 소음 8, 노양 9○, 노음 6✕)
   - ① 본괘(本卦) 성립 및 상징 의미
   - ② 변효(動爻) 및 지괘(之卦) 도출 및 상징 의미

3. 고변점(考變占) 및 체용(體用) 해석 규칙 적용
   - 동효 개수별 주자 고변점 규칙 적용 내역 (예: 동효가 2개일 때 상층부 효사 채택)
   - 체(體, 본괘 대전제)와 용(用, 지괘 미래 지향점)의 흐름 명시

4. 괘사·효사 종합 해석 및 실질적 조언
   - ① 현재 상황 진단 (본괘상 및 내담자 시공간적 위치 풀이)
   - ② 핵심 행동 지침 (주 주요 해석 대상 + 한문 효사 원문 + 현대적 실천 해설)
   - ③ 보조 경계 지침 (함께 동한 효사 + 한문 효사 원문 + 조급함 경계 조언)
   - ④ 미래의 귀결 및 주의점 (지괘 대상전/괘사 + 한문 원문 + 내실 양육 지침)
   - 💡 질문자에 대한 최종 종합 컨설팅 요약 (한문 원문 인용 + 결론 강조)
```

---

## 🏗️ 3계층 하이브리드 서버리스 아키텍처

```mermaid
flowchart TD
    subgraph Client ["클라이언트 (내담자)"]
        Browser[Next.js Modern Zen Web UI]
    end
    
    subgraph Vercel ["Vercel Edge (Seoul icn1)"]
        NextApp[Next.js 16 App Router]
        AuthCallback[/auth/callback 클라이언트 페이지]
    end
    
    subgraph Supabase ["Supabase Cloud (Seoul ap-northeast-2)"]
        Auth[Supabase Auth - Google OAuth]
        DB[(PostgreSQL 16 + pgvector)]
        RLS[RLS & 50 웰컴 크레딧 자동 지급]
    end
    
    subgraph CloudRun ["Google Cloud Run (Seoul asia-northeast3)"]
        FastAPI[FastAPI 백엔드 컨테이너 - Non-root]
        JWTAuth[JWT 서명 검증 & Rate Limiter]
        Engine[주자 변효 규칙 엔진]
        Pipeline[멀티에이전트 오케스트레이션]
    end
    
    subgraph AI ["Google Cloud Vertex AI"]
        Gemini[Gemini 2.5 Flash\nthinking_budget=0 / 3초 지연]
    end

    Browser -->|1. Google 소셜 로그인 & 세션 발급| Auth
    Browser -->|2. 웹 페이지 렌더링| NextApp
    Browser -->|3. 상담 API 호출 - Bearer JWT 헤더| FastAPI
    FastAPI -->|4. JWT 서명 검증 & user_id 확정| JWTAuth
    FastAPI -->|5. 2,536건 송대 주석 균형 검색| DB
    FastAPI -->|6. 64괘 386효 규칙 엔진 & 에이전트 추론| Gemini
    FastAPI -->>Browser: 7. 4단계 고품격 리포트, 성찰 질문, 실시간 근거 반환
```

---

## 🤖 멀티에이전트 파이프라인 구조

```
[0] 안전 스크리닝 (Safety Screener)
    - 사용자 발화 및 위기 신호 감지
    - 위기 감지 시 괘 도출 없이 즉시 공공 핫라인 안내로 분기 (BLOCK_CRISIS)
    - 24시간 사용자 래치(CRISIS_LATCH_HOURS)로 우회 차단
            ↓ (정상 통과 시)
[1] 접수·정리 에이전트 (Intake Agent)
    - 고민 구체화 및 카테고리 분류
    - 동일 질문 재도출(재삼독 몽괘 원칙) 감지 및 이전 괘 인계
            ↓
[2] 괘 도출·해석 에이전트 (Interpretation Agent)
    - 규칙 엔진(core.hexagram_engine)으로 6효 및 동효(노양/노음) 산출
    - 주자 점법(Focus Rule)에 따라 DB 1:1 확정 괘사·효사 조회
    - RAG(core.rag)를 통해 정전(程傳 1,752건) 및 본의(本義 784건) 균형 검색
            ↓
[★] 리포트 에이전트 (Report Agent v0.3.0 - NEW)
    - 내담자 질문, 6효 수리 배열, 고변점 룰, 한문 효사 원문, RAG 주석 융합
    - 4단계 고품격 1:1 맞춤 주역 컨설팅 보고서 구조화 JSON 집필
            ↓
[3] 상담 에이전트 (Counsel Agent - 5턴 소크라테스 코칭 모델 v0.5.0)
    - 성리학 자성(自省)과 경(敬) 철학 기반 5단계 코칭 (화두 → 맹점 → 처방 → 미래 → 실천 다짐)
    - 5턴 하드 가드레일 (`is_final: true`)로 무한 꼬리물기 대화 원천 차단
    - 4 Quality Gates 자아비판(Critique & Refinement) 루프로 상투어 0건 억제
            ↓ (5턴 완료 시)
[★] 액션 카드 v2 렌더러 (Action Card Generator v2 - NEW)
    - 1가지 구체적 실천 다짐(Action Pledge) 구조화 및 캔버스 그래픽 카드 생성
    - 안전 암호화 카드 내보내기 지원
            ↓
[+1] 저널 에이전트 (Journal Agent)
    - 전체 대화 요약, 핵심 성찰 및 실천 질문(Action Items) DB 기록
```

---

## 🛡️ 제로 트러스트 보안 & 엔지니어링 최적화

| 영역 | 도입 기술 및 최적화 내용 | 효과 |
|---|---|---|
| **인증 및 신원 검증** | Supabase JWT 서명 검증 (`PyJWT`, `HS256`, `aud="authenticated"`) | `user_id` 위조, 위기 래치 우회 및 BOLA(세션 탈취) 원천 방어 |
| **동시성 원장 안전성** | 조건부 원자적 `UPDATE` (`credit_balance >= amount` + `RETURNING`) | 크레딧 차감 시 레이스 컨디션(Race Condition) 100% 방어 |
| **추론 속도 최적화** | Gemini 2.5 Flash `types.ThinkingConfig(thinking_budget=0)` | 1턴 지연시간 **18초 ➔ 3초 (6배 단축)** |
| **토큰 다이어트** | 대화 이력 슬라이딩 윈도우 (최근 3턴/6발화) 및 불필요한 필드 압축 | 긴 세션 토큰 소모 **50% 이상 절감** (1세션 원가 약 1.5~3원) |
| **DoS 및 과금 방어** | 슬라이딩 윈도우 Rate Limiter (IP/사용자당 1분 30회) + 메모리 자동 정리 | 비인가 호출 및 Financial DoS 방어 |
| **컨테이너 하드닝** | Dockerfile 비루트 사용자(`appuser:1000`) 실행 및 진입점 고정 | 컨테이너 이탈 및 루트 권한 탈취 방지 |
| **정보 노출 방지** | OWASP 표준 보안 헤더 + 에러 스택트레이스 마스킹 | 민감한 인프라 내부 정보 클라이언트 노출 차단 |

---

## 💻 기술 스택

### Backend
- **Python 3.9+ / FastAPI**: 비동기 REST API 서버 (라우터 모듈화: `api/routers/{counsel,card,safety}.py`)
- **Google Cloud Run**: 서울 리전(`asia-northeast3`) 무상태 컨테이너 (0~10 Scale-to-Zero)
- **SQLAlchemy (AsyncIO) / asyncpg**: 비동기 PostgreSQL ORM (다중 DB 호환 `UUIDType` 적용)
- **Google GenAI / Vertex AI (Gemini 2.5 Flash)**: 멀티에이전트 LLM 파이프라인
- **PyJWT**: Supabase JWT 서명 검증 및 인증 의존성

### Database & RAG
- **Supabase Cloud (PostgreSQL 16 + pgvector)**: 서울 리전(`ap-northeast-2`)
- **HNSW 벡터 인덱스**: 송대 이천역전(정전) 1,752건 + 주역본의(본의) 784건 = **2,536건 주석 벡터**
- **RLS (Row Level Security)**: SELECT Only 권한 및 사용자별 데이터 격리

### Frontend
- **Next.js 16 (App Router, Turbopack)**: Vercel 서울 리전(`icn1`) 배포
- **React 19 / TypeScript**
- **Tailwind CSS / Framer Motion / Lucide React**
- **Modern Zen UI**: 주역 6효 애니메이션, 4단계 고품격 리포트 뷰어, 5턴 소크라테스 대화 인터페이스, 실천 액션 카드 모달 렌더러, 실시간 크레딧 잔액 배지 동기화

---

## 🚀 빠른 시작 (Getting Started)

### 1. 환경 설정

```bash
# 저장소 복제
git clone https://github.com/casareborgia/IChing-AI-Consultant.git
cd IChing-AI-Consultant

# 가상환경 생성 및 의존성 설치
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 프론트엔드 의존성 설치
cd frontend
npm install
cd ..
```

### 2. 환경 변수 설정 (`.env` 및 `env.production.yaml`)

- 로컬 개발용 `.env` 설정 (예시: `.env.example` 참조)
- 프로덕션 배포 시: `env.production.yaml.example`을 복사하여 `env.production.yaml`을 생성하고 실제 GCP 프로젝트 ID와 배포 도메인을 입력합니다.

```env
# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/iching

# Gemini / Vertex AI
LLM_PROVIDER=gemini
GEMINI_MODEL=gemini-2.5-flash
GOOGLE_CLOUD_PROJECT=your-gcp-project-id

# Supabase JWT Secret (검증용)
SUPABASE_JWT_SECRET=your-supabase-jwt-secret
```

### 3. 백엔드 실행

```bash
.venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8008 --reload
```

### 4. 프론트엔드 실행

```bash
cd frontend
npm run dev
```

브라우저에서 **`http://localhost:3000`**에 접속하여 상담을 시작할 수 있습니다.

---

## 🧪 테스트 및 벤치마크

본 프로젝트는 150개 이상의 자동화 테스트 스위트와 Codex/CI 검증을 위한 표준 평가 하네스를 제공합니다:

```bash
# 1. 전체 단위 및 보안 통합 테스트 실행 (150개 케이스 전수 검증 100% PASS)
.venv/bin/pytest -v

# 2. 크레딧 동시성(Race Condition) 및 결제 가드 전용 테스트
.venv/bin/pytest tests/test_credit_system.py -v

# 3. 5턴 소크라테스 상담 6대 핵심 KPI 측정기 가동
.venv/bin/python scripts/evaluate_counsel_kpi.py --mock --json

# 4. JWT 인증 및 BOLA 방어 전용 테스트
.venv/bin/pytest tests/test_jwt_auth.py -v

# 5. 안전 스크리닝 채점 벤치마크 (115건)
.venv/bin/python scripts/score_safety.py -p gemini
```

> **종합 평가 가이드**: 프로젝트 전체에 대한 정량적 감사 기준 및 평가 루브릭은 [`docs/PROJECT_EVALUATION_KPI.md`](docs/PROJECT_EVALUATION_KPI.md)를 참조하십시오.

---

## 📄 라이선스 및 고지사항

- 본 서비스는 의료기기(SaMD) 또는 전문 심리치료를 대체하지 않으며, 자기 성찰과 의사결정을 돕는 웰니스 AI 도구입니다.
- 위기 상황 발생 시 24시간 자살예방 상담전화(`109`) 또는 정신건강 위기상담전화(`1577-0199`)의 도움을 받으실 수 있습니다.

### 라이선스 (코드와 데이터가 다릅니다)

| 대상 | 라이선스 | 파일 |
|---|---|---|
| 소스 코드 | **MIT License** (자유로운 사용, 수정 및 2차 배포 가능) | [`LICENSE`](LICENSE) |
| `data/` 텍스트 및 파생물 | **CC BY-SA 4.0** (출처 표기 및 동일 조건 변경 허락 계승) | [`data/PROVENANCE.md`](data/PROVENANCE.md) |

소스 코드는 MIT License 조건 하에 자유롭게 활용 가능하며, 데이터셋 및 원전 자료는 CC BY-SA 4.0 저작권 표시 조건을 따릅니다.
