# 주역 상담 AI (프로젝트 컨텍스트)

## 한 줄 정의
주역 괘를 뽑아 해석하되, **1회성 운세가 아니라 되묻고 깊어지는 상담 대화**를 제공하는 앱.

## 포지셔닝 (설계 판단의 기준)
- "고급 타로/사주"가 **아님**. 예언이 아니라 **변화를 읽는 의사결정 지원 도구**.
- AI 톤: 예언자 ❌ / 상담사 ⭕. 단정짓지 말고 함께 들여다보는 태도.
- 근거 투명성이 차별점 — 왜 이 해석인지 원문 근거를 댈 수 있어야 함.

## 아키텍처 (멀티에이전트)

```
[0] 안전 스크리닝    위기 신호 감지 → 감지 시 괘 도출 없이 즉시 지원 안내로 분기
        ↓ (통과)
[1] 정리 에이전트    고민 명확화 + 중복질문(재삼독) 감지
        ↓
[2] 괘 도출·해석     규칙 엔진으로 괘 산출 → 원문 DB 조회 → RAG로 관련 해설 검색
        ↓
[3] 상담 에이전트    대화체 재구성 + 되묻기 판단 (↺ 자기 루프)
        ↓ (세션 종료 시, 비동기)
[+1] 저널 에이전트   요약 저장 → 다음 세션 컨텍스트로 활용
```

**중요:** [3]은 파이프라인의 끝이 아니라 **루프**다. 한 번에 결론 내지 않는다.

## 데이터 레이어 구분 (헷갈리기 쉬움)

| 레이어 | 처리 방식 | RAG? |
|---|---|---|
| 괘/효 도출 | 규칙 알고리즘 | ❌ |
| 괘사·효사 원문 | DB 단순 조회 (1:1 고정) | ❌ |
| 주석·현대해설·상담사례 | 의미 기반 검색 | ✅ |
| 정신의학 자료 | **설계 참고용, RAG 인덱스 제외** | ❌ |

정신의학 자료를 RAG에 넣으면 AI가 검색해서 진단성 발언을 하게 됨 → 절대 금지.

## 보유 자산

- `data/hexagrams.json` — 64괘 / 384효 구조화 완료 (파싱 검증 통과)
  - 원문(괘사·효사·단전·대상전·소상전·문언전) + 정전(程傳) 주석 1,251블록
  - **한문 원문만 있음. 한글 번역 없음** ← 최우선 과제
  - 주자 『본의(本義)』 미포함 ← 추가 확보 필요
- `scripts/parse_jeonguiu.py` — 위 JSON을 만든 파서 (재실행 가능)

## 기술 스택
- 모델: Gemma 4 26B (MoE, Apache 2.0)
- 배포: Google Cloud (Vertex AI + Cloud SQL)
- 로컬 개발: Mac Mini M4 Pro + Ollama + Docker Compose
- IDE: Google Antigravity + Claude Code

## DB 결정 (확정)
- **Postgres 16 + pgvector** (별도 벡터DB 없이 통합)
- 선택 이유: 쓰기 동시성 / 벡터검색 통합 / Cloud Run·Cloud SQL 호환
- ORM: SQLAlchemy 2.0 (async, asyncpg 드라이버)
- 마이그레이션: Alembic
- 로컬 구동: `docker compose up -d` → localhost:5432
- 활성 확장: vector, pgcrypto, pg_trgm

## 작업 순서 (의존성 순)

1. [x] DB 스키마 확정 — 나머지 전부가 여기 의존
2. [x] 괘 도출 규칙 엔진 (기존 코드 이식 + 단위테스트)
3. [ ] 괘사·효사 한글 번역 384건 (API 배치, 노트북LM 아님)
4. [ ] RAG 청크 구축 (해설·사례만, 원문 제외)
5. [ ] 에이전트 4종 + 안전 스크리닝 구현
6. [ ] 로컬 통합 테스트 (GCP 올리기 전 여기서 다 잡기)
7. [ ] Vertex AI 배포 + 비용/지연 실측

## 디렉토리 구조

```
iching-counsel/
├── CLAUDE.md
├── BACKLOG.md            # 좋은 아이디어는 코드가 아니라 여기로
├── docker-compose.yml    # Postgres + pgvector (로컬)
├── .env.example
├── db/
│   └── init/
│       └── 01_extensions.sql
├── data/
│   └── hexagrams.json
├── scripts/
│   └── parse_jeonguiu.py
├── agents/               # intake, interpret, counsel, journal, safety
├── core/                 # hexagram_engine, db, rag
├── schemas/              # Pydantic 모델
├── migrations/           # Alembic
└── prompts/              # 에이전트별 프롬프트 (코드와 분리)
```

## 스키마 초안 (Pydantic)

```python
class IntakeOutput(BaseModel):
    clarified_question: str
    topic_category: str
    is_duplicate_question: bool
    duplicate_session_ref: str | None

class HexagramInterpretation(BaseModel):
    hexagram_id: int
    changing_lines: list[int]
    raw_text: str              # DB 조회 확정값
    contextual_mapping: str    # 사용자 상황 매핑 초안

class CounselTurn(BaseModel):
    message: str
    needs_followup: bool       # True면 루프 반복
    followup_question: str | None
    is_final: bool             # True면 저널 에이전트로 핸드오프
```

## 설계 원칙 (지킬 것)

1. **원문은 그대로 노출하지 않는다** — 사용자 상황 언어로 재구성. 인용은 1문장 이내.
2. **같은 질문 재뽑기 금지** — 주역 몽괘 "재삼독즉불고" 원칙. 대신 이전 상담을 다시 보여주거나 "무엇이 달라졌는지" 되묻는다.
3. **RAG는 1회 검색으로 끝내지 않는다** — 대화 중 필요하면 재검색(Agentic RAG).
4. **진단하지 않는다** — 병명·약물·의학적 판단 언급 금지.
5. **아이디어는 BACKLOG.md로** — 스코프 확장은 코드에 손대기 전에 기록만.

## 법적 확인 사항 (배포 전)
- [ ] 주역전의 텍스트 출처 사이트 이용약관 (표점·편집 저작권)
- [ ] 앱 내 고지: "의학적·심리적 치료를 대체하지 않습니다"
- [ ] 위기 대응 안내 연락처 확인
