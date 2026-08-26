# 주역 심층 AI 상담 (I-Ching AI Consultant)

> 주역 64괘와 송대 주석(정전·본의)에 기반하여, 단순한 점괘가 아닌 **삶의 변화를 읽고 성찰하는 심층 멀티턴 대화형 의사결정 상담 앱**

---

## 🌟 프로젝트 개요

**I-Ching AI Consultant**는 사용자의 고민을 경청하고, 주자 점법 규칙 엔진을 통해 괘를 도출한 뒤, 전통 원문(괘사·효사)과 주석(이천역전·주역본의)을 현대적 심리 상담 언어로 풀어내는 AI 상담 시스템입니다.

- **포지셔닝**: 미래를 단정 짓는 '예언자'가 아닌, 스스로 내면의 답을 찾도록 돕는 **'의사결정 지원 동반자이자 거울'**
- **근거 투명성**: AI의 환각(Hallucination) 없이 DB 1:1 확정 원문과 RAG 주석을 프론트엔드 근거 패널에 투명하게 공개
- **다계층 안전망**: 위기 상황(자살/자해, 폭력, 응급) 감지 시 즉각 개입 없이 공공 핫라인(109, 1577-0199 등)으로 안전하게 이관

---

## 🏗️ 시스템 아키텍처

```
[0] 안전 스크리닝 (Safety Screener)
    - 사용자 발화 및 위기 신호 감지
    - 위기 감지 시 괘 도출 없이 즉시 공공 핫라인 안내로 분기 (BLOCK_CRISIS)
            ↓ (정상 통과 시)
[1] 접수·정리 에이전트 (Intake Agent)
    - 고민 구체화 및 카테고리 분류
    - 동일 질문 재도출(재삼독 몽괘 원칙) 감지 및 이전 괘 인계
            ↓
[2] 괘 도출·해석 에이전트 (Interpretation Agent)
    - 규칙 엔진(core.hexagram_engine)으로 6효 및 동효(노양/노음) 산출
    - 주자 점법(Focus Rule)에 따라 DB 1:1 확정 괘사·효사 조회
    - RAG(core.rag)를 통해 정전(程傳) 및 본의(本義) 주석 검색
    - 효사의 형상/위치/고유 의미(3개 슬롯) 기반 상황 매핑 생성
            ↓
[3] 상담 에이전트 (Counsel Agent)
    - 주역 상징을 현대적 상담 대화체로 재구성 (1턴 1핵심질문 성찰 유도)
    - 종료 신호(감사, 생각 정리) 감지 시 자연스러운 상담 마무리
            ↓ (세션 완료 시)
[+1] 저널 에이전트 (Journal Agent)
    - 상담 요약 및 핵심 통찰(Insight) 기록 → 다음 상담 컨텍스트 활용
```

---

## 🛡️ 안전망 및 위기 대응 시스템

- **2024년 통합 기준 한국 위기상담 리소스 DB 구축 (`core/crisis_resources.py`)**:
  - `109` 자살예방 상담전화 (24시간)
  - `1577-0199` 정신건강 위기상담전화 (24시간)
  - `1388` 청소년 상담전화 (24시간)
  - `1366` 여성긴급전화 (24시간)
- **발화 정황 맞춤 연계**: 청소년(`minor`), 폭력 피해(`violence`), 일반(`general`) 정황에 따라 우선순위 최적화 안내
- **위기 래치 (`CRISIS_LATCH_HOURS`)**: 위기 판정 발생 시 세션 차단 고정 및 안전 지원 지속
- **상담 종결 오탐 방지**: 상담 마무리 소회 및 감사 인사("생각이 정리되었습니다. 고맙습니다")는 정상 발화로 정확히 분류

---

## 💻 기술 스택

### Backend
- **Python 3.9+ / FastAPI**: 비동기 REST API 서버
- **SQLAlchemy (AsyncIO) / SQLite**: 세션, 턴 이력, 64괘 및 386효 원문 DB
- **Google GenAI / Vertex AI (Gemini 2.5 Flash)**: 멀티에이전트 LLM 파이프라인
- **Qdrant / Custom Vector Store**: 송대 이천역전(정전) 1,752건 및 주역본의(본의) 784건 RAG 임베딩

### Frontend
- **Next.js 16 (App Router, Turbopack)**
- **React 19 / TypeScript**
- **Tailwind CSS / Framer Motion / Lucide React**
- **Modern Zen UI**: 주역 6효 애니메이션, 동효(노양/노음) 변화 시각화, 실시간 근거 패널

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
GOOGLE_API_KEY=your_gemini_api_key
# 또는 Google Cloud Vertex AI 인증 설정
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

브라우저에서 **`http://localhost:3001`** (또는 `http://localhost:3000`)에 접속하여 상담을 시작할 수 있습니다.

---

## 🧪 테스트 및 벤치마크

```bash
# 1. 전체 단위 테스트 실행 (113개 케이스)
.venv/bin/pytest -q

# 2. 안전 스크리닝 채점 벤치마크 (115건)
.venv/bin/python scripts/score_safety.py -p gemini

# 3. 에이전트 형식 및 제약 벤치마크
.venv/bin/python scripts/score_agents.py -p gemini

# 4. 괘별 차별성 및 상용구 측정
.venv/bin/python scripts/compare_hexagram_effect_turns.py -p gemini -n 1
```

---

## 📄 라이선스 및 고지사항

- 본 서비스는 의료기기 또는 전문 심리치료를 대체하지 않으며, 자기 성찰과 의사결정을 돕는 웰니스 AI 도구입니다.
- 위기 상황 발생 시 24시간 자살예방 상담전화(`109`) 또는 정신건강 위기상담전화(`1577-0199`)의 도움을 받으실 수 있습니다.

### 원전 출처

주역 원문, 정전(程傳) 및 본의(本義) 주석 텍스트는 **Kanseki Repository (漢籍リポジトリ),
교토대학 인문과학연구소**의 표점본을 저본으로 하며 **CC BY-SA 4.0**으로 제공됩니다.

- 경문 `KR1a0001` · 정전 `KR1a0016` 『伊川易傳』 · 본의 `KR1a0031` 『原本周易本義』
- 저본 저작(정이 1033–1107, 주희 1130–1200)은 보호기간이 만료된 공유 영역 자료입니다.
- 괘사·효사 한글 번역 450건은 이 저장소에서 자체 생성한 것입니다.

취득 경위와 판정 근거는 [`data/PROVENANCE.md`](data/PROVENANCE.md)에 있습니다.
