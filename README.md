# 주역 심층 AI 상담 (I-Ching AI Consultant)

> 주역 64괘와 송대 주석(이천역전·주역본의)에 기반하여, 단순한 점괘가 아닌 **삶의 변화를 읽고 성찰하는 심층 멀티턴 대화형 의사결정 상담 AI**

[![Architecture](https://img.shields.io/badge/Architecture-3--Tier_Serverless-blue?style=flat&logo=googlecloud)](https://github.com/casareborgia/IChing-AI-Consultant)
[![Framework](https://img.shields.io/badge/Frontend-Next.js_16-black?style=flat&logo=nextdotjs)](https://github.com/casareborgia/IChing-AI-Consultant)
[![Backend](https://img.shields.io/badge/Backend-FastAPI_v1.0-009688?style=flat&logo=fastapi)](https://github.com/casareborgia/IChing-AI-Consultant)
[![Tests](https://img.shields.io/badge/Tests-128_Passed-brightgreen?style=flat&logo=pytest)](https://github.com/casareborgia/IChing-AI-Consultant)
[![Security](https://img.shields.io/badge/Security-Zero_Trust_JWT-emerald?style=flat&logo=auth0)](https://github.com/casareborgia/IChing-AI-Consultant)
[![License: Code](https://img.shields.io/badge/Code-All_Rights_Reserved-red?style=flat)](LICENSE)
[![License: Data](https://img.shields.io/badge/Data-CC_BY--SA_4.0-lightgrey?style=flat)](data/LICENSE)

---

## 🌟 프로젝트 개요

**I-Ching AI Consultant**는 사용자의 고민을 경청하고, 주자 변효 규칙 엔진을 통해 괘를 도출한 뒤, 전통 원문(괘사·효사)과 송대 주석(정전·본의 2,536건)을 현대적 심리 상담 언어로 풀어내는 AI 상담 시스템입니다.

- **포지셔닝**: 미래를 단정 짓는 '예언자'가 아닌, 스스로 내면의 답을 찾도록 돕는 **'의사결정 지원 동반자이자 거울'**
- **근거 투명성 (Provenance)**: AI 환각(Hallucination) 없이 DB 1:1 확정 원문과 pgvector RAG 주석을 프론트엔드 근거 패널에 투명하게 공개
- **다계층 안전망 & SaMD 웰니스**: 위기 신호(자살/자해, 폭력) 감지 시 괘 도출을 차단하고 24시간 자살예방 상담전화(`109`)로 즉시 안전 이관 (24시간 위기 래치 적용)
- **제로 트러스트 보안 (Zero-Trust)**: 요청 본문 `user_id`를 불허하고, Supabase JWT 서명 검증(`HS256`, `audience="authenticated"`)을 통해 신원을 강제 확정하여 위기 래치 및 세션 소유권(BOLA) 변조를 원천 차단

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
    FastAPI -->>Browser: 7. 괘 도출, 성찰 질문, 실시간 근거 반환
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
    - 효사의 형상/위치/고유 의미(3개 슬롯) 기반 상황 매핑 생성
            ↓
[3] 상담 에이전트 (Counsel Agent)
    - 주역 상징을 현대적 상담 대화체로 재구성 (1턴 1핵심질문 성찰 유도)
    - 종료 신호(감사, 생각 정리) 감지 시 자연스러운 상담 마무리
            ↓ (세션 완료 시)
[+1] 저널 에이전트 (Journal Agent)
    - 전체 대화 요약, 핵심 성찰 및 실천 질문(Action Items) DB 기록
```

---

## 🛡️ 제로 트러스트 보안 & 엔지니어링 최적화

| 영역 | 도입 기술 및 최적화 내용 | 효과 |
|---|---|---|
| **인증 및 신원 검증** | Supabase JWT 서명 검증 (`PyJWT`, `HS256`, `aud="authenticated"`) | `user_id` 위조, 위기 래치 우회 및 BOLA(세션 탈취) 원천 방어 |
| **추론 속도 최적화** | Gemini 2.5 Flash `types.ThinkingConfig(thinking_budget=0)` | 1턴 지연시간 **18초 ➔ 3초 (6배 단축)** |
| **토큰 다이어트** | 대화 이력 슬라이딩 윈도우 (최근 3턴/6발화) 및 불필요한 필드 압축 | 긴 세션 토큰 소모 **50% 이상 절감** (1세션 원가 약 1.5~3원) |
| **DoS 및 과금 방어** | 슬라이딩 윈도우 Rate Limiter (IP/사용자당 1분 30회) + 메모리 자동 정리 | 비인가 호출 및 Financial DoS 방어 |
| **컨테이너 하드닝** | Dockerfile 비루트 사용자(`appuser:1000`) 실행 및 진입점 고정 | 컨테이너 이탈 및 루트 권한 탈취 방지 |
| **정보 노출 방지** | OWASP 표준 보안 헤더 + 에러 스택트레이스 마스킹 | 민감한 인프라 내부 정보 클라이언트 노출 차단 |

---

## 💻 기술 스택

### Backend
- **Python 3.9+ / FastAPI**: 비동기 REST API 서버
- **Google Cloud Run**: 서울 리전(`asia-northeast3`) 무상태 컨테이너 (0~10 Scale-to-Zero)
- **SQLAlchemy (AsyncIO) / asyncpg**: 비동기 PostgreSQL ORM
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
- **Modern Zen UI**: 주역 6효 애니메이션, 동효(노양/노음) 변화 시각화, 실시간 근거 패널, 50 웰컴 크레딧 배지

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

### 2. 환경 변수 설정 (`.env`)

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

```bash
# 1. 전체 단위 및 보안 통합 테스트 실행 (120개 케이스 전수 검증)
.venv/bin/pytest -q

# 2. JWT 인증 및 소유권 차단 전용 테스트
.venv/bin/pytest tests/test_jwt_auth.py -v

# 3. 안전 스크리닝 채점 벤치마크 (115건)
.venv/bin/python scripts/score_safety.py -p gemini

# 4. 에이전트 형식 및 제약 벤치마크 (24/24 전수 통과)
.venv/bin/python scripts/score_agents.py -p gemini

# 5. 본의 주석 톤 영향 및 예언 단정성 검증 (단정적 표현 0건)
.venv/bin/python scripts/compare_benui_tone.py -p gemini
```

---

## 📄 라이선스 및 고지사항

- 본 서비스는 의료기기(SaMD) 또는 전문 심리치료를 대체하지 않으며, 자기 성찰과 의사결정을 돕는 웰니스 AI 도구입니다.
- 위기 상황 발생 시 24시간 자살예방 상담전화(`109`) 또는 정신건강 위기상담전화(`1577-0199`)의 도움을 받으실 수 있습니다.

### 라이선스 (코드와 데이터가 다릅니다)

| 대상 | 라이선스 | 파일 |
|---|---|---|
| 소스 코드 | **전권 유보 (All rights reserved).** 열람용으로 공개되어 있을 뿐 오픈소스가 아닙니다 | [`LICENSE`](LICENSE) |
| `data/` 텍스트 및 파생물 | **CC BY-SA 4.0** (계승 조건 포함) | [`data/LICENSE`](data/LICENSE) |

코드의 복제·2차 저작물 작성·서비스 운영에는 저작권자의 사전 서면 허락이 필요합니다.

### 원전 출처
주역 원문, 정전(程傳) 및 본의(本義) 주석 텍스트는 **Kanseki Repository (漢籍リポジトリ), 교토대학 인문과학연구소**의 표점본을 저본으로 합니다.
- 경문 `KR1a0001` · 정전 `KR1a0016` 『伊川易傳』 · 본의 `KR1a0031` 『原本周易本義』
- 저본 저작(정이 1033–1107, 주희 1130–1200)은 보호기간이 만료된 퍼블릭 도메인(공유 영역) 자료입니다.
- 괘사·효사 450건의 현대 한글 번역 데이터는 본 프로젝트에서 자체 감수·구축하였습니다.
- 취득 경위와 세부 판정 근거는 [`data/PROVENANCE.md`](data/PROVENANCE.md)를 참조합니다.

