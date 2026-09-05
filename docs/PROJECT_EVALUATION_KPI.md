# 주역 AI 성찰 상담 서비스 (I-Ching Oracle)
# 종합 엔지니어링 & 서비스 품질 평가 KPI 프레임워크 (Codex Audit Suite)

> **문서 버전**: v1.0.0  
> **작성 일시**: 2026-09-06  
> **평가 주체**: Codex (Claude Code / AI Auditor)  
> **대상 시스템**: Next.js 16 (Vercel) + FastAPI (GCP Cloud Run) + Supabase (PostgreSQL 16 + pgvector) + Gemini 2.5 Flash / Gemma

---

## 1. 평가 개요 및 목적

본 문서는 **주역 AI 성찰 상담 서비스**의 현재까지 구현된 전체 시스템(고전 원전 데이터, 역학 엔진, 멀티에이전트 파이프라인, 안전 스크리너 및 SaMD 컴플라이언스, 백엔드 동시성/원장 결제, 클라우드 인프라, 테스트 자동화)을 **Codex(평가자)**가 객관적·정량적으로 검증하고 점수를 부여할 수 있도록 표준화한 종합 KPI(Key Performance Indicators) 평가 프레임워크입니다.

### 평가 원칙
1. **재현성 (Reproducibility)**: 모든 정량 지표는 제공된 CLI 명령어 및 테스트 스위트를 통해 로컬 환경에서 즉시 재현 가능해야 합니다.
2. **원인 격리 (Isolation)**: 인덱스 내용, LLM 프롬프트, 백엔드 로직의 결함이 서로 섞이지 않도록 독립 하네스를 기반으로 측정합니다.
3. **규제 안전성 (Regulatory & Compliance)**: 식약처 SaMD(의료기기) 비의료용 웰니스 가이드라인 및 자살예방 위기 대응 기준을 절대 준수해야 합니다.
4. **금융/원장 무결성 (Zero-Tolerance Concurrency)**: 크레딧 차감 시 레이스 컨디션 및 BOLA(Broken Object Level Authorization) 취약점이 0건이어야 합니다.

---

## 2. 6대 평가 영역 및 핵심 KPI 매트릭스

```
+-----------------------------------------------------------------------------------+
|                        [I-Ching AI Consultant] 종합 KPI 체계                      |
+-----------------------------------------------------------------------------------+
| [D1] 고전 데이터 & 주역 엔진 무결성  | [D2] 안전성 & SaMD 규제 컴플라이언스       |
|  - 64괘 386효 원전 1:1 무결성       |  - 위기 스크리닝 적중률 (치명미탐 0%)      |
|  - 2,536건 RAG 주석 적재 균형       |  - 24시간 위기 래치 & 100% 자동 환불      |
|  - 주자 점법 & 체용 오행 100%       |  - 의료 진단 표현 0건 (SaMD 웰니스)       |
+-------------------------------------+---------------------------------------------+
| [D3] 멀티에이전트 상담 품질         | [D4] 백엔드 동시성 & 보안 무결성            |
|  - 5턴 소크라테스 코칭 정렬도       |  - 크레딧 차감 원자적 UPDATE 레이스 차단   |
|  - 상투어/클리셰 0건 억제           |  - 다중 DB 호환 UUIDType 적용               |
|  - 괘별 차별성 (다른괘 공유율 <8%)  |  - Supabase JWT & BOLA 원천 차단            |
+-------------------------------------+---------------------------------------------+
| [D5] 인프라, 성능 및 비용 효율      | [D6] 테스트 자동화 및 코드 품질             |
|  - 응답 지연 시간 (턴당 <= 15s)     |  - Pytest 회귀 테스트 전수 통과 (150+ 건)  |
|  - 세션당 토큰 마진율 (> 95%)       |  - 검증 하네스 스크립트 실행 정합성         |
|  - Scale-to-Zero 무중단 배포        |  - 타입 힌팅 및 모듈화 아키텍처             |
+-------------------------------------+---------------------------------------------+
```

---

## 3. 세부 KPI 정의 및 검증 사양서

### [Domain 1] 고전 데이터 및 주역 엔진 무결성 (가중치: 15%)

| KPI 코드 | 지표명 | 목표치 (Target) | 기준선/현재치 | 검증 방법 및 명령어 |
| :--- | :--- | :---: | :---: | :--- |
| **KPI-1.1** | **원전 데이터 및 표점 무결성** | 100% (오차 0건) | 64괘 / 386효 원문 966, 주석 1,251블록 일치 | `python scripts/verify_kanripo.py`<br>`pytest tests/test_parser.py tests/test_translations.py` |
| **KPI-1.2** | **고전 국역 충실도 및 한자 잔여 억제** | 한자 잔여 ≤ 2건 | 450건 전수 국역 완료, 한자 잔여 2건 이하 | `pytest tests/test_translations.py -k "test_450건이_빠짐없이_채워졌다 or test_용어표"` |
| **KPI-1.3** | **정전·본의 RAG 균형 적재율** | 2,536건 (정전 1,752 + 본의 784) | 총 2,536건 분리 적재 및 쿼터 분리 검색 (`search_balanced`) | `pytest tests/test_rag_balance.py` |
| **KPI-1.4** | **주자 점법 및 체용 규칙 알고리즘 정확도** | 100% | 0~6 동효 초점 산출 및 체용 생극 독립 판정 100% | `pytest tests/test_hexagram_engine.py` |

- **Pass 기준**: 위 4개 항목 모두 100% 통과 (데이터 손상 및 알고리즘 변조 0건).

---

### [Domain 2] 안전성 및 SaMD 규제 컴플라이언스 (가중치: 20%)

| KPI 코드 | 지표명 | 목표치 (Target) | 기준선/현재치 | 검증 방법 및 명령어 |
| :--- | :--- | :---: | :---: | :--- |
| **KPI-2.1** | **위기 스크리닝 치명 미탐률 (False Negative)** | **0.0% (0건)** | 0건 (115개 벤치마크 중 치명 놓침 0) | `pytest tests/test_agents_safety.py -k "위기_감지"`<br>`python scripts/score_safety.py -p gemini` |
| **KPI-2.2** | **안전 벤치마크 정확도** | ≥ 95.0% (110/115) | 110/115 달성 (과탐 0건) | `python scripts/score_safety.py -p gemini` (또는 mock 하네스) |
| **KPI-2.3** | **위기 래치 및 100% 자동 환불 보장** | 100% | 24시간 래치 유지, 위기 시 10C 즉시 환불 | `pytest tests/test_credit_system.py -k "test_crisis_turn_is_refunded"` |
| **KPI-2.4** | **SaMD 웰니스 준수 및 라벨 비노출** | 100% (위반 0건) | `BLOCK_CRISIS` 등 내부 등급 노출 0건, 의료 진단 단어 차단 | `pytest tests/test_agents_safety.py -k "사용자_출력에_내부_라벨_미노출"` |

- **Pass 기준**: KPI-2.1(치명 미탐률) 0% 미달 시 즉시 전체 평가 **FAIL** 처리.

---

### [Domain 3] 멀티에이전트 상담 품질 및 상투어 억제 (가중치: 20%)

| KPI 코드 | 지표명 | 목표치 (Target) | 기준선/현재치 | 검증 방법 및 명령어 |
| :--- | :--- | :---: | :---: | :--- |
| **KPI-3.1** | **5턴 소크라테스 턴 정렬도** | ≥ 95.0% | 100.0% (Mock 기준) | `python scripts/evaluate_counsel_kpi.py --mock` |
| **KPI-3.2** | **상투어/클리셰 배제율** | 100.0% | "주역에서는 지금의 상황을" 35회→7회 급감 | `pytest tests/test_boilerplate_metrics.py`<br>`python scripts/evaluate_counsel_kpi.py --mock` |
| **KPI-3.3** | **단정적 예언 표현 0건율** | 100% (0건) | 예언 표현 0건 (정전/본의 대조 실측 0건 유지) | `pytest tests/test_divination_chat_engine.py` |
| **KPI-3.4** | **5턴 하드 가드레일 (무한루프 차단)** | 100% | 턴 5 도달 시 `is_final: true` 강제 종결 | `pytest tests/test_divination_chat_engine.py -k "test_5턴_하드_터미네이션_보장"` |
| **KPI-3.5** | **괘별 고유성 및 다른 괘 공유율** | 공유율 ≤ 8.0% | 5.0% 달성 (답변 차이 대조군 +0.199) | `pytest tests/test_hexagram_effect_metrics.py` |

- **Pass 기준**: 종합 품질 지수 ≥ 90점 및 하드 가드레일 100% 충족.

---

### [Domain 4] 백엔드 동시성, 결제 원장 및 보안 (가중치: 20%)

| KPI 코드 | 지표명 | 목표치 (Target) | 기준선/현재치 | 검증 방법 및 명령어 |
| :--- | :--- | :---: | :---: | :--- |
| **KPI-4.1** | **크레딧 차감 동시성(Race Condition) 방어율** | **100% (초과차감 0건)** | 동시 8건 요청 시 잔액 엄밀 방어 (원자적 UPDATE) | `pytest tests/test_credit_system.py -k "test_concurrent"` |
| **KPI-4.2** | **잔액 부족 402 가드 및 원장 정합성** | 100% | 잔액 < 10C 시 HTTP 402 반환, 입출금 원장 누적 | `pytest tests/test_credit_system.py -k "insufficient or overspend"` |
| **KPI-4.3** | **다중 DB 호환 UUIDType 무결성** | 100% | PostgreSQL UUID ↔ SQLite CHAR(36) 듀얼 호환 | `pytest tests/test_db_integration.py` |
| **KPI-4.4** | **Supabase JWT 인증 및 BOLA 차단율** | **100% (위반 0건)** | Bearer JWT 필수, 토큰 위조/만료 시 401 차단 | `pytest tests/test_jwt_auth.py` |

- **Pass 기준**: 동시성 초과 인출 발생 시 즉시 전체 평가 **FAIL** 처리.

---

### [Domain 5] 인프라, 성능 및 비용 효율성 (가중치: 10%)

| KPI 코드 | 지표명 | 목표치 (Target) | 기준선/현재치 | 검증 방법 및 명령어 |
| :--- | :--- | :---: | :---: | :--- |
| **KPI-5.1** | **상담 대화 턴당 응답 지연 (Latency)** | ≤ 15.0초 | 초기 45초 → 약 11~14초 (Gemini Flash) | `api/routers/counsel.py` 스트리밍/추론 파이프라인 실측 |
| **KPI-5.2** | **세션당 토큰 효율 및 비즈니스 마진율** | 마진율 ≥ 90% | 세션당 입력 5.8k / 출력 1.1k 토큰 (마진율 > 95%) | `scripts/measure_session.py -p ollama` |
| **KPI-5.3** | **Cloud Run 서버리스 가동성** | Scale-to-Zero 무중단 | Cloud Run Seoul 리전 배포 정상 동작 | `curl -f https://iching-counsel-api-517419857386.asia-northeast3.run.app/health` |
| **KPI-5.4** | **프론트엔드 실시간 크레딧 동기화** | 지연 0건 | 턴 완료 시 API 잔액 수신 즉시 UI 상태 반영 | `frontend/src/context/AuthContext.tsx` 및 `page.tsx` 연동 |

- **Pass 기준**: 지연 시간 15초 이내 및 마진율 90% 이상 유지.

---

### [Domain 6] 테스트 자동화 및 코드베이스 건전성 (가중치: 15%)

| KPI 코드 | 지표명 | 목표치 (Target) | 기준선/현재치 | 검증 방법 및 명령어 |
| :--- | :--- | :---: | :---: | :--- |
| **KPI-6.1** | **Pytest 자동화 테스트 통과율** | **100% (150+ 건 통과)** | 150 passed, 4 skipped (실DB 연결 제외), 0 failed | `./.venv/bin/python -m pytest` |
| **KPI-6.2** | **평가 및 벤치마크 하네스 가동률** | 100% | 안전·상담·상투어 측정 CLI 스크립트 8종 정상 실행 | `scripts/evaluate_counsel_kpi.py --mock` 등 |
| **KPI-6.3** | **코드 아키텍처 및 정적 품질** | Pydantic v2 / Clean Architecture | 라우터, 에이전트, 코어 모델, 스키마 계층 분리 완료 | 코드베이스 구조 검토 (`api/`, `agents/`, `core/`) |

---

## 4. 종합 평가 점수 산출 공식 및 판정 등급

### 4.1 종합 점수(Overall Audit Score) 산출식
$$\text{Overall Score} = \sum_{k=1}^{6} \left( \text{Domain Score}_k \times \text{Weight}_k \right)$$

| 평가 영역 (Domain) | 배점 (가중치) | 주요 판정 기준 |
| :--- | :---: | :--- |
| **D1. 고전 데이터 & 주역 엔진** | **15점** | 원전 1:1 일치, 고전 국역 450건, RAG 2,536건, 주자 점법 |
| **D2. 안전성 & SaMD 컴플라이언스** | **20점** | 치명 미탐 0%, 벤치마크 ≥95%, 래치/환불, 비진단 원칙 |
| **D3. 멀티에이전트 상담 품질** | **20점** | 5턴 소크라테스, 상투어 0%, 예언 0%, 5턴 하드 종료 |
| **D4. 백엔드 동시성 & 보안** | **20점** | 원자적 UPDATE 레이스 차단, 402 가드, JWT & BOLA 차단 |
| **D5. 인프라 & 비용 효율** | **10점** | 턴당 지연 ≤15초, 세션 마진율 >90%, Cloud Run/Vercel |
| **D6. 테스트 자동화 & 코드 품질**| **15점** | Pytest 100% 통과, 벤치마크 스크립트 가동성 |
| **총계 (Total)** | **100점** | 만점 기준 |

### 4.2 최종 판정 등급 (Grade Rubric)

| 등급 (Grade) | 점수 범위 | 조치 및 배포 승인 여부 |
| :---: | :---: | :--- |
| **Grade S (Exemplary)** | **95.0점 ~ 100.0점** | **즉시 프로덕션 배포 및 대외 공개 승인 (Approved for Launch)** |
| **Grade A (Pass)** | **90.0점 ~ 94.9점** | **상용 서비스 적합 (Minor 리팩터 권고 후 배포 가능)** |
| **Grade B (Warning)** | 80.0점 ~ 89.9점 | 배포 보류. 미흡 지표에 대한 핫픽스 스프린트 요구 |
| **Grade F (Fail)** | 79.9점 이하 | **배포 금지 (치명적 결함 발견 시 점수 무관 FAIL)** |

> [!CAUTION]
> **즉시 과락(Auto-Fail) 조건 (Zero-Tolerance Gates)**:
> 1. 위기 스크리닝 치명 미탐(`False Negative`) 발생 시
> 2. 크레딧 차감 동시성 레이스 컨디션으로 인한 초과 인출 결함 발생 시
> 3. 인증 우회 또는 BOLA를 통해 타인 계정 세션/크레딧 침범 가능 시
> 4. Pytest 회귀 테스트 실패 발생 시

---

## 5. Codex를 위한 단계별 평가 실행 가이드 (Audit Protocol)

Codex(평가자)는 아래 4단계 절차를 순차적으로 실행하여 채점을 진행하십시오.

### Step 1: 단위 및 통합 테스트 전수 검증 (D1, D4, D6)
```bash
# 가상환경 파이썬으로 pytest 실행
./.venv/bin/python -m pytest -v
```
- **판정 기준**: 150건 이상 PASS, 0건 FAIL 확인.

### Step 2: 크레딧 동시성 및 보안 심층 검증 (D4)
```bash
# 동시성 레이스 컨디션 및 402 가드 테스트 집중 검증
./.venv/bin/python -m pytest tests/test_credit_system.py tests/test_jwt_auth.py -v
```
- **판정 기준**: `test_concurrent_starts_cannot_overspend` 및 `test_concurrent_turns_cannot_overspend` 통과 필수.

### Step 3: 5턴 상담 품질 및 가드레일 지표 측정 (D3)
```bash
# 상담 6대 핵심 KPI 측정기 실행
./.venv/bin/python scripts/evaluate_counsel_kpi.py --mock --json
```
- **판정 기준**: `Hard_Termination_Rate` 100%, `Cliche_Free_Rate` 100%, 종합 점수 ≥ 90점 확인.

### Step 4: 원전 데이터 무결성 및 고전 번역 검증 (D1)
```bash
# 고전 450건 번역 및 데이터 무결성 검증
./.venv/bin/python -m pytest tests/test_translations.py tests/test_hexagram_engine.py -v
```
- **판정 기준**: 원문 변조 0건, 주자 점법 산출 100% 일치 확인.

---

## 6. 결론 및 평가 요약 리포트 템플릿

Codex 평가 완료 후, 아래 템플릿 형식으로 최종 리포트를 산출합니다:

```markdown
# [Codex Audit Report] 주역 AI 성찰 상담 앱 종합 평가 결과

- **평가 일시**: 2026-XX-XX
- **평가자**: Codex AI Auditor
- **종합 점수**: XX / 100 점
- **최종 판정**: [ PASS (Grade S) / PASS (Grade A) / FAIL ]

### 도메인별 점수 요약
1. 고전 데이터 & 주역 엔진 무결성: XX / 15 점
2. 안전성 & SaMD 컴플라이언스: XX / 20 점
3. 멀티에이전트 상담 품질: XX / 20 점
4. 백엔드 동시성 & 보안 무결성: XX / 20 점
5. 인프라, 성능 및 비용 효율성: XX / 10 점
6. 테스트 자동화 & 코드베이스 품질: XX / 15 점

### 종합 감사 의견
- ...
```
