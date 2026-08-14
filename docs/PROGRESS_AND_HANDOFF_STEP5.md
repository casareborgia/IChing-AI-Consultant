# 🧭 주역 상담 AI — 진행 현황 및 5단계 작업 인수인계서 (HANDOFF)

> **기준 시점**: 2026-08-14 (Step 1 ~ Step 4 완료)  
> **현재 브랜치**: `main` (최신 커밋: `f372186` 머지 완료)  
> **테스트 상태**: `pytest` 20개 테스트 전체 통과 (100% Pass)

---

## 📌 1. 지금까지 완료된 작업 요약 (Step 1 ~ Step 4)

| 단계 | 주요 작업 내용 | 핵심 파일 / 산출물 | 상태 |
|---|---|---|---|
| **Step 1: DB 스키마 & 인프라** | Postgres 16 + pgvector 환경 구축, SQLAlchemy 2.0 비동기 모델, Alembic 마이그레이션 | `core/models/`, `db/`, `docker-compose.yml`, `alembic.ini` | ✅ 완료 |
| **Step 2: 괘 도출 규칙 엔진** | 척전법(동전)/대연수법(시초), 변효 계산, 본괘/지괘 매핑, 주자 점법 Focus Rule 구현 | `core/hexagram_engine.py`, `schemas/hexagram_engine.py` | ✅ 완료 |
| **Step 3: 본문 450건 한글 번역** | 괘사 64건 + 효사 386건 전수 번역, 용어표 확정, 13건 결함 교차 보정, DB 적재 | `data/translations/`, `scripts/load_translations.py`, `pilot/` | ✅ 완료 |
| **Step 4: RAG 청크 1,751건 구축** | 정전 주석 1,251건 + 소상전 386건 + 단전/대상전 128건 번역, Vertex AI 임베딩 & pgvector 적재 | `data/rag_chunks.json`, `scripts/embed_chunks.py`, `scripts/search_chunks.py` | ✅ 완료 |

---

## 📂 2. 현재 주요 파일 및 데이터 구조

```
주역기반상담앱/
├── CLAUDE.md                   # 프로젝트 전체 마스터 설계 컨텍스트
├── BACKLOG.md                  # 아이디어 및 백로그
├── data/
│   ├── hexagrams.json          # 64괘/386효 한문 원문 및 구조화 데이터
│   ├── translation_items.json  # 450건 번역 대상 원본
│   ├── translations/
│   │   ├── claude.json         # 450건 Claude 번역본
│   │   ├── gemini.json         # 450건 Gemini 번역본
│   │   ├── overrides.json      # 결함 13건 보정본
│   │   └── chunks_claude.json  # 1,751건 RAG 청크 번역본
│   └── rag_chunks.json         # 1,751건 RAG 청크 원문
├── core/
│   ├── config.py               # 설정 (Vertex AI, DB, 리전 등)
│   ├── db.py                   # AsyncSessionLocal
│   ├── hexagram_engine.py      # 괘 산출 및 변효/포커스 규칙 엔진
│   └── models/                 # SQLAlchemy 모델 (hexagram, rag, counsel)
├── schemas/                    # Pydantic 입출력 스키마
├── scripts/
│   ├── demo_reading.py         # 괘 도출 + DB 원문/한글 조회 통합 데모
│   ├── search_chunks.py        # RAG 자연어 의미 검색 스크립트
│   ├── demo_cast.py            # 순수 괘 도출 규칙 데모
│   ├── load_translations.py    # 450건 번역 DB 적재기
│   └── embed_chunks.py         # 1,751건 RAG 임베딩 DB 적재기
└── tests/                      # 20개 전수 검증 테스트
```

---

## 🎯 3. 다음 작업: Step 5 멀티에이전트 파이프라인 구현

다음 작업 세션에서는 `agents/` 디렉토리에 **4종 에이전트 + 안전 스크리닝 모듈**을 구현합니다.

### 🔄 에이전트 호출 파이프라인

```
[0] safety.py (안전 스크리닝)
     │   · 위기 신호(자해, 극단선택, 응급 위급상황) 감지
     │   · 감지 시: 괘 도출 없이 즉시 전문 지원기관 안내로 긴급 분기
     ↓ (정상 통과 시)
[1] intake.py (정리 에이전트)
     │   · 사용자 고민 구체화 및 명확화
     │   · 중복 질문(재삼독: 再三瀆) 감지 (같은 질문 반복 시 이전 상담 소환 또는 변화 되묻기)
     ↓
[2] interpret.py (해석 에이전트)
     │   · core.hexagram_engine 규칙 엔진으로 괘 산출
     │   · DB에서 확정 괘사/효사 한글 번역 조회
     │   · RAG(pgvector)로 해당 괘/효에 맞는 주석·해설 검색
     │   · 사용자 상황과 괘 원문의 맥락 매핑 초안 생성
     ↓
[3] counsel.py (상담 에이전트) ↺ [대화 루프]
     │   · 원문을 그대로 읊지 않고 사용자 상황 언어로 재구성
     │   · 단정적 예언 ❌ / 질문을 던지는 상담사 태도 ⭕
     │   · needs_followup 판단을 통해 되묻기 대화 루프 수행
     ↓ (세션 종료 시, 비동기)
[+1] journal.py (저널 에이전트)
         · 상담 세션 요약 및 핵심 인사이트 DB 저장
         · 다음 상담 시 맥락(Context)으로 활용
```

---

## ⚠️ 4. 에이전트 구현 시 반드시 지켜야 할 원칙 ([CLAUDE.md](file:///Users/leeseungjun/coding/주역기반상담앱/CLAUDE.md))

1. **원문 노출 최소화**: 한문 원문은 그대로 나열하지 않고 사용자의 고민 언어로 자연스럽게 녹여낸다 (인용은 1문장 이내).
2. **단정·예언 금지**: AI는 "미래를 맞히는 점쟁이"가 아니라 "변화의 맥락을 함께 짚어주는 상담사" 톤을 유지한다.
3. **진단 및 의료 행위 절대 금지**: 정신의학적 병명, 약물, 의학적 판단 언급 금지.
4. **동일 질문 재뽑기 금지 (재삼독)**: 몽괘 원칙에 따라 동일 고민을 반복 질문하면 다시 뽑지 않고 이전 상담을 되돌아보게 유도한다.
5. **RAG 인덱스 분리 준수**: 정신의학 자료는 RAG에 넣지 않으며, 주역 주석 및 상담 사례만 참조한다.

---

## 🧪 5. 검증 명령어 치트시트

```bash
# 가상환경 활성화
source .venv/bin/activate

# 1. 전체 테스트 실행 (현재 20개 통과 상태)
pytest -v

# 2. 괘 도출 및 DB 연동 통합 데모 실행
python scripts/demo_reading.py

# 3. RAG 의미 검색 실행
python scripts/search_chunks.py "기다려야 할까" --hexagram 5 -k 3
```
