# 주역 기반 성찰형 상담 AI (I-Ching Oracle)
## 개발 위키 및 시행착오·개선사항 회고록 (Step 1 ~ Step 5)

> **최종 업데이트**: 2026-08-16  
> **상태**: 5단계 멀티에이전트 완성 및 Google ADK(Agent Development Kit) 리팩토링 완료 (78개 단위/통합 테스트 100% 통과)

---

## 1. 프로젝트 개요 및 핵심 철학

### 1.1. 한 줄 정의
주역 64괘 384효의 상(象)과 사(辭)를 바탕으로 하되, **1회성 운세·점술이 아닌 내담자가 스스로의 상황을 깊이 들여다보고 성찰하도록 돕는 의사결정 지원 멀티에이전트 상담 AI**.

### 1.2. 핵심 설계 원칙 (포지셔닝)
1. **예언자 ❌ / 상담사 ⭕**: 단정적 미래 예측이나 공포 마케팅을 철저히 배제하고, "변화의 흐름을 읽는 조력자"로서 1턴 1질문 되묻기(Reflective Inquiry)를 수행합니다.
2. **근거 투명성 (Provenance)**: 모든 해석은 주역 원문 및 역사적 주석(정전·본의)에 기반하며, 내담자가 질문 시 정확한 문헌 근거를 제시할 수 있어야 합니다.
3. **한문 원문 노출 차단**: 모델에게 한문 텍스트를 주지 않고 감수된 현대 한글 번역만 전달하여, 한문이 답변에 새어나오거나 난해해지는 것을 원천 차단합니다.
4. **의료기기(SaMD) 판정선 준수**: 특정 정신질환 병명(우울증, 공황장애 등)이나 진단성 발언을 절대 하지 않으며, 코드 레벨에서 이를 강제 차단합니다.

---

## 2. 시스템 아키텍처 및 멀티에이전트 구조

```
[0] 안전 스크리닝 (Safety)      위기 신호 감지 시 괘 도출 없이 즉시 핫라인 안내로 분기 (24시간 사용자 래치)
         ↓ (통과)
[1] 정리 에이전트 (Intake)      고민 명확화 + 중복 질문(재삼독/몽괘 원칙) 감지 시 이전 상담 회고 분기
         ↓ (신규 고민)
[2] 괘 도출·해석 (Interpret)    주자 변효 규칙 엔진 괘 산출 → DB 1:1 확정 원문 → pgvector RAG 주석 균형 검색
         ↓
[3] 상담 에이전트 (Counsel)      1턴 1질문 되묻기 대화 루프 (↺ 다중 턴) + 근거 질문 시 자동 재검색 인용
         ↓ (세션 종료 시)
[+1] 저널 에이전트 (Journal)     전체 대화 요약, 핵심 성찰 및 실천 질문(Action Items) DB 저장
```

---

## 3. 데이터 레이어 및 RAG 구축 경과

### 3.1. 저본(Text Base) 전면 이관 (2026-08-15)
- **배경**: 초기 사용했던 현토본의 현대 저작권 이슈 및 오탈자 문제를 해결하기 위해, 국제 표준 오픈 코퍼스인 **Kanseki Repository(漢籍리포지토리) 표점본**(`KR1a0001` 경문 + `KR1a0016` 이천역전 정전)으로 전면 교체.
- **작업**: 64괘 386효(괘사 64 + 효사 386 = 450건) 한글 번역 완료 및 DB 적재.

### 3.2. 주자 『본의(本義)』 784건 추가 적재 (2026-08-16)
- **배경**: 조선 이래 주역의 표준인 **전의(傳義: 정전+본의)** 체제를 온전히 갖추고, 엔진의 주자 변효 판정 기준의 문헌적 근거를 보강하기 위해 原本周易本義(`KR1a0031`) 784건을 별도 파싱 및 임베딩.
- **총 RAG 인덱스**: **2,536건** (정전 계열 1,752건 + 본의 784건).
- **균형 검색 (`search_balanced`)**: 한 풀에서 검색 순위가 쏠리는 현상을 막기 위해 괘 단위(정전 3 + 본의 2), 초점 효 단위(정전 2 + 본의 1)로 몫을 갈라 검색.

---

## 4. Google ADK (`google/adk-python`) 표준 리팩토링 (2026-08-16)

기존의 절차적 파이썬 함수 구조를 Google 공식 **Agent Development Kit** 표준에 맞춰 리팩토링하여 Cloud Run 배포 최적화를 달성했습니다.

| 모듈 | 파일 경로 | 주요 역할 |
|---|---|---|
| **ADK Tools** | `agents/tools.py` | `cast_hexagram_tool`, `lookup_hexagram_text_tool`, `search_iching_commentaries_tool`, `lookup_past_sessions_tool` |
| **ADK Base** | `agents/adk/base.py` | `Agent`, `Tool`, `InvocationContext` ADK 호환 추상화 |
| **ADK Agents** | `agents/adk/*.py` | `safety`, `intake`, `interpret`, `counsel`, `journal` 개별 에이전트 인스턴스 |
| **Workflow Runner** | `agents/adk/workflow.py` | `IChingADKWorkflow`: 멀티에이전트 오케스트레이션 및 무결성 제어 |
| **Session Service** | `agents/adk/session_service.py` | `PostgresADKSessionService`: Cloud SQL/Postgres 세션 영속성 관리 |
| **배포 컨테이너** | `Dockerfile` | Python 3.11-slim 기반 Cloud Run scale-to-zero 무상태 컨테이너 설정 |

---

## 5. 주요 시행착오(Troubleshooting) 및 개선사항

### ① Ollama 컨텍스트 윈도우(4096) 한계로 인한 JSON 잘림
- **문제**: 로컬 Gemma 4 모델이 프롬프트가 길어질 때 JSON 출력이 도중에 잘려 상담 답변이 폴백 문구로 나감.
- **원인**: Ollama 서버가 기본 `num_ctx`를 4096으로 제한하고 있었음.
- **해결**: `core/llm.py`에서 Ollama 요청 시 `options={"num_ctx": 16384}`를 명시적으로 주입하여 해결.

### ② 안전 스크리너와 성찰 마무리 신호('정리')의 충돌
- **문제**: 상담을 정상적으로 마치며 내담자가 *"생각이 정리가 좀 됐어요"*라고 하자, 안전 스크리너가 이를 '신변 정리(자살 징후)'로 오인하여 위기 차단(BLOCK_CRISIS) 안내를 내보냄.
- **원인**: 위기 시험셋에 '정리'가 전부 물건/신변 정리 사례만 존재했고, '생각/마음의 정리' 사례가 없었음.
- **해결**: 스크리너 프롬프트에 '정리의 목적어'에 따른 구분 규칙(생각·마음 정리 = 정상 성찰, 신변·재산 정리 = 위기)을 명시하고, 채점셋에 성찰 마무리 문장을 추가하여 해결.

### ③ 위기 차단 판정의 세션 래치(Latch) 무력화 문제
- **문제**: 위기 발화로 세션이 차단(`is_final=True`)된 후, 사용자가 곧바로 새 세션을 열면 이전 위기 기록이 조회되지 않아 괘가 정상 발급되는 보안 구멍 발생.
- **해결**: `_has_recent_crisis()` 함수를 통해 세션뿐 아니라 **사용자 ID 기준 24시간 래치(`CRISIS_LATCH_HOURS`)**를 두어 기간 내 모든 재접속을 차단하도록 수정.

### ④ 의료/진단성 어휘의 프롬프트 누출 위험 (SaMD 방지)
- **문제**: 프롬프트에 "병명을 말하지 말라"고 지시해도 간헐적으로 모델이 "우울증 초기 증상" 등의 표현을 생성함.
- **해결**: 프롬프트 의존을 버리고 코드 레벨에서 `find_diagnosis_terms()` 정규식 검사를 수행하여, 진단어 발견 시 즉시 안전한 성찰형 전환 문장(`DIAGNOSIS_FALLBACK`)으로 덮어쓰도록 강제.

### ⑤ 내담자의 근거 질문 시 모델 자율 재검색 실패
- **문제**: 내담자가 *"왜 그렇게 해석하나요?"*라고 물어도 모델이 자율적으로 `search_query`를 생성해 재검색하지 않고 기존 한 줄을 앵무새처럼 반복함.
- **해결**: `asks_for_grounds()` 발화 패턴 검사 함수를 두어, 근거 질문이 들어오면 코드가 강제로 정전/본의 주석을 재검색하여 프롬프트에 주입하고 인용하도록 구현.

### ⑦ Gemini 2.5 Flash Thinking 토큰 최적화 및 무손실 토큰 다이어트 (2026-08-26)
- **문제**: Gemini 2.5 Flash가 불필요한 Thinking 토큰을 소모하여 과금 증가 및 지연시간 발생, `max_output_tokens` 초과 시 간헐적 JSON 잘림 에러 발생.
- **해결**:
  1. `types.ThinkingConfig(thinking_budget=0)` 설정으로 사고 토큰 과금 완전 제거 및 1턴 응답 속도 **약 18초 ➔ 약 3초 (6배 단축)** 달성.
  2. **대화 이력 슬라이딩 윈도우 (최근 3턴 6개 발화)** 적용으로 긴 세션에서의 토큰 50% 이상 절감.
### ⑧ 제로 트러스트(Zero Trust) 보안 아키텍처 구축 (2026-08-26)
- **문제**: BOLA(세션 무단 접근) 취약점, 무제한 API 호출로 인한 Financial DoS 위험, 500 에러 내부 정보 노출, 컨테이너 루트 실행 보안 취약점 존재.
- **해결**:
  1. **세션 소유권 검증 (BOLA 방지)**: `CounselSession.user_id`와 요청자 `user_id`를 엄격 대조하여 불일치 시 `HTTP 403` 즉시 차단.
  2. **Rate Limiter (DoS/과금 폭탄 방어)**: IP당 1분 최대 30회 슬라이딩 윈도우 제한 적용 (`HTTP 429`).
  3. **엄격한 입력 검증**: Pydantic Field를 통한 발화 길이(`max_length=1000`) 및 식별자 정규식 검증.
  4. **내부 에러 마스킹 (Information Disclosure 방지)**: 상세 스택트레이스를 서버 로거에만 남기고 클라이언트에는 일반화된 메시지만 반환.
  5. **CORS 도메인 명시적 제어**: 환경변수 `CORS_ORIGINS` 기반 프로덕션 origin 화이트리스트 분리.
  6. **컨테이너 보안 하드닝**: `Dockerfile` 내 비루트 사용자(`appuser:1000`) 실행 및 진입점 고정.

---

## 6. 테스트 및 벤치마킹 기준선 (Baseline)

| 검증 항목 | 도구/스크립트 | 결과 | 비고 |
|---|---|---|---|
| **단위/통합 테스트** | `.venv/bin/pytest` | **115/115 Passed (100%)** | Mock/Engine/Security 115개 전수 통과 |
| **에이전트 제약/형식 하네스** | `scripts/score_agents.py -p gemini` | **형식 24/24 · 제약 24/24 (100%)** | Gemini 2.5 Flash 1턴 지연 약 3초 |
| **본의 주석 톤 영향 검증** | `scripts/compare_benui_tone.py -p gemini` | **단정적 예언 표현 0건** | 주자 본의 적재 후에도 상담사 톤 유지 |

---

## 7. 배포 및 향후 로드맵 (Next Steps)

상세 설계는 [통합 배포 및 수익화 블루프린트 문서](file:///Users/leeseungjun/coding/주역기반상담앱/docs/DEPLOYMENT_AND_MONETIZATION_BLUEPRINT.md)를 참조합니다.

1. **상용 추론 엔진 & 토큰 다이어트 완료 (2026-08-26)**:
   - Gemini 2.5 Flash API / Vertex AI 직결 연동 및 지연시간 3초대 단축
   - 무손실 토큰 다이어트 적용 완료
2. **제로 트러스트 보안 패치 완료 (2026-08-26)**:
   - 세션 소유권 검증, Rate Limiting, 입력 검증, 에러 마스킹, 비루트 컨테이너 하드닝
3. **SaMD 웰니스 규제 및 라이선스 고지 완료 (2026-08-27)**:
   - `safety_category` 외부 노출 제거, 109 핫라인 웰니스 면책 박스 및 Kanripo CC BY-SA 4.0 표기 강화
4. **Modern Zen 마이크로 랜딩 및 웰컴 배지 구현 완료 (2026-08-27)**:
   - 3단계 성찰 대화 프로세스 가이드, 3대 철학 차별점, 50 웰컴 크레딧 배지 및 프로모션 배너 구현
5. **통합 클라우드 3계층 배포 및 보안 구축 완료 (2026-08-28)**:
   - **1단계 (DB)**: Supabase Seoul 데이터베이스 구축 (64괘, 386효, 2,536건 HNSW 벡터 청크 주입 완료, `match_chunks` RPC 생성)
   - **2단계 (Backend)**: Google Cloud Run 무상태 컨테이너 배포 (`iching-counsel-api`, 서울 리전 `asia-northeast3`, Gemini 2.5 Flash 연동, 0~10 오토스케일링)
   - **3단계 (Frontend)**: Next.js 16 Vercel 배포 설정 (`vercel.json`), Supabase Auth(카카오/Google OAuth) 연동, 로그인 필수 게이트(Auth Gate) 적용
   - **보안 하드닝 (`/sec`)**: 자체 보안 스캐너(0 Issues Clean), BOLA 방지 소유권 엄격 대조, OWASP 표준 보안 헤더, 1MB 페이로드 제한, Supabase RLS SELECT Only 잠금

---

## 🧭 향후 작업 로드맵 (Next Action Items)

> **최종 업데이트**: 2026-08-29

### ✅ 오늘 완료 (2026-08-28~29)

| 항목 | 상태 | 내용 |
|---|---|---|
| **카카오 OAuth 실키 등록** | ✅ 완료 | REST API Key + Client Secret → Supabase Kakao Provider 활성화 |
| **Google OAuth 실키 등록** | ✅ 완료 | Web Client ID + Secret → Supabase Google Provider 활성화 |
| **Vercel 프로덕션 배포** | ✅ 완료 | https://i-ching-ai-consultant.vercel.app 라이브 |
| **NEXT_PUBLIC_SITE_URL 환경변수** | ✅ 완료 | Vercel 프로젝트 환경변수 등록 완료 |

### 🔴 내일 이어서 (P1 마무리)

1. **Supabase URL Configuration 업데이트**
   - Site URL: `https://i-ching-ai-consultant.vercel.app`
   - Redirect URL 추가: `https://i-ching-ai-consultant.vercel.app/auth/callback`
2. **카카오/구글 Redirect URI 등록 확인**
   - 카카오: `https://developers.kakao.com/console/app/1560078/product/login`
   - 구글: Google Cloud Console OAuth 클라이언트
3. **E2E 로그인 테스트**: 프로덕션에서 카카오/구글 로그인 → 50 크레딧 지급 → 상담 시작 실측

### 2. 사용자 경험(UX) 강화: '나의 성찰 저널 보관함' (P2)
- **히스토리 보관함 (`/journals`)**:
  - 로그인 사용자가 과거 상담 세션(본괘/지괘, 3턴 대화록, 성찰 저널)을 다시 열람할 수 있는 아카이빙 페이지 구축
  - Supabase `counsel_sessions`, `counsel_turns` 테이블과 실시간 연동

### 3. 운영 & KPI 지표 수집 파이프라인 (P3)
- **GA4 / PostHog 이벤트 트래킹**:
  - 상담 시작율 → 괘 도출율 → 3턴 완주율 → 저널 보관율 퍼널 지표 수집
- **관리자 KPI 대시보드**:
  - Supabase DB 통계 기반 일일 상담 건수, 크레딧 소모량, DAU 대시보드 구현

### 4. 수익화(BM) 인프라: 크레딧 결제 및 충전 연동 (P4 - 최후순위)
- **PortOne / 토스페이먼츠 연동**:
  - 50 웰컴 크레딧 소진 시 충전 모달 팝업 (예: 50크레딧 2,900원 / 100크레딧 4,900원)
  - 결제 승인 웹훅을 통한 `credit_ledger` 자동 충전 트랜잭션 및 `deduct_credit` RPC 연동

- **Google Cloud Console**: OAuth Client ID / Secret 발급 $\rightarrow$ Supabase Auth Provider 등록
- **Kakao Developers**: 카카오 로그인 활성화, REST API 키 및 Client Secret 등록
- **Vercel 실도메인 배포**: GitHub 저장소 연결 및 환경변수 3종 등록, 프로덕션 도메인 확정
- **OAuth Callback 검증**: 실제 카카오/구글 로그인 $\rightarrow$ 50 웰컴 크레딧 자동 지급 E2E 실측

### 2. 사용자 경험(UX) 강화: '나의 성찰 저널 보관함' (P2)
- **히스토리 보관함 (`/journals`)**:
  - 로그인 사용자가 과거 상담 세션(본괘/지괘, 3턴 대화록, 성찰 저널)을 다시 열람할 수 있는 아카이빙 페이지 구축
  - Supabase `counsel_sessions`, `counsel_turns` 테이블과 실시간 연동

### 3. 수익화(BM) 인프라: 크레딧 결제 및 충전 연동 (P3)
- **PortOne / 토스페이먼츠 연동**:
  - 50 웰컴 크레딧 소진 시 충전 모달 팝업 (예: 50크레딧 2,900원 / 100크레딧 4,900원)
  - 결제 승인 웹훅을 통한 `credit_ledger` 자동 충전 트랜잭션 및 `deduct_credit` RPC 연동

### 4. 운영 & KPI 지표 수집 파이프라인 (P4)
- **GA4 / PostHog 이벤트 트래킹**:
  - 상담 시작율 $\rightarrow$ 괘 도출율 $\rightarrow$ 3턴 완주율 $\rightarrow$ 저널 보관율 퍼널 지표 수집
- **관리자 KPI 대시보드 (`building-data-apps`)**:
  - Supabase DB 통계 기반 일일 상담 건수, 크레딧 소모량, 활성 사용자(DAU) 대시보드 구현

