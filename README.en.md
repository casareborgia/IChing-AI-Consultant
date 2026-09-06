# I-Ching AI Consultant

> Grounded in the 64 hexagrams of the I-Ching and Song-dynasty commentaries (Yichuan Yizhuan, Zhouyi Benyi) — a **multi-turn conversational decision-support counselor** that reads change and prompts reflection, not a fortune teller.

[![Architecture](https://img.shields.io/badge/Architecture-3--Tier_Serverless-blue?style=flat&logo=googlecloud)](https://github.com/casareborgia/IChing-AI-Consultant)
[![Frontend](https://img.shields.io/badge/Frontend-Next.js_16-black?style=flat&logo=nextdotjs)](https://github.com/casareborgia/IChing-AI-Consultant)
[![Backend](https://img.shields.io/badge/Backend-FastAPI_v1.0-009688?style=flat&logo=fastapi)](https://github.com/casareborgia/IChing-AI-Consultant)
[![Tests](https://img.shields.io/badge/Tests-167_Passed-brightgreen?style=flat&logo=pytest)](https://github.com/casareborgia/IChing-AI-Consultant)
[![Socratic Counsel](https://img.shields.io/badge/Socratic_Counsel-v0.5.0_5Turn_ActionCard-gold?style=flat&logo=openai)](https://github.com/casareborgia/IChing-AI-Consultant)
[![Security](https://img.shields.io/badge/Security-Zero_Trust_JWT-emerald?style=flat&logo=auth0)](https://github.com/casareborgia/IChing-AI-Consultant)
[![License: Code](https://img.shields.io/badge/Code-MIT_License-blue?style=flat)](LICENSE)
[![License: Data](https://img.shields.io/badge/Data-CC_BY--SA_4.0-lightgrey?style=flat)](data/PROVENANCE.md)

[한국어](README.md) · **English**

---

## 🌟 Overview

**I-Ching AI Consultant** listens to the user's situation, derives a hexagram through a Zhu Xi changing-line rule engine, and renders the classical source text (hexagram and line statements) plus 2,536 Song-dynasty commentary entries into the language of modern reflective counseling.

- **Positioning**: not a prophet who fixes the future, but a **decision-support companion and mirror** that helps users find their own answers.
- **Five-turn Socratic coaching engine (v0.5.0)**: a five-stage Socratic model grounded in Neo-Confucian self-examination (自省) and Toegye's philosophy of reverence (敬). A hard five-turn guardrail (`is_final: true`) prevents endless follow-up loops, and a four-gate critique-and-refinement pass suppresses clichés in favor of high-register Korean prose.
- **Action Card v2 with canvas renderer (v0.5.0)**: on completing five turns, the user's single concrete action pledge is structured and rendered as a shareable graphic card, with encrypted export.
- **1:1 personalized consulting report**: a dedicated `Report Agent` built on the TCREI framework fuses six-line numerology, Zhu Xi's *gobyeonjeom* (考變占) rules, Chinese source text of line statements from the database, and RAG-retrieved classical commentary into a **four-part report**, then binds its conclusions into the `Counsel Agent` conversation.
- **Report context persistence**: the full report written on the first turn is stored on the session (`counsel_sessions.report_data`) and re-injected into every subsequent turn's prompt, so later answers never contradict the first report's action guidance or closing summary. Generation state is tracked via `report_status` (`ready` / `failed` / `not_requested`) and `report_error_code`.
- **Provenance**: no hallucinated sources. Verbatim database text and pgvector RAG commentary are exposed in a frontend evidence panel.
- **Layered safety net & SaMD wellness stance**: on detecting crisis signals (suicide, self-harm, violence), hexagram derivation is blocked and the session is handed off to Korea's 24-hour suicide prevention line (`109`), with a 24-hour crisis latch and automatic full credit refund.
- **Zero-trust security**: `user_id` in the request body is rejected outright; identity is established by verifying the Supabase JWT signature (`HS256`, `audience="authenticated"`), closing off crisis-latch bypass and session-ownership (BOLA) tampering.

---

## 📋 Four-Part Consulting Report Structure (Report Agent v4.1)

> The report format the backend LLM (Gemini) writes from scratch for each user's situation — fully variable, no fixed templates.

```markdown
1. Question & Mindset Setting
   - Fully reflects the querent's own account
   - States the jaesamdok (再三瀆) taboo: one sincere casting, free of self-interest

2. Hexagram Derivation (numerology and line stacking)
   - Values for lines 1 through 6 (young yang 7, young yin 8, old yang 9○, old yin 6✕)
   - (i) The original hexagram and its symbolic meaning
   - (ii) Changing lines and the resulting transformed hexagram

3. Gobyeonjeom (考變占) and Body-Function (體用) Interpretation Rules
   - Which Zhu Xi rule applies for the given number of changing lines
   - The flow between body (體, the original hexagram's premise) and function (用, the transformed hexagram's direction)

4. Integrated Interpretation and Practical Guidance
   - (i) Diagnosis of the present situation
   - (ii) Core action guidance (focal line + Chinese source text + modern application)
   - (iii) Auxiliary cautions (co-changing line + source text + counsel against haste)
   - (iv) Future outcome and cautions (transformed hexagram's statements + source text)
   - Closing consulting summary with source-text citation
```

---

## 🏗️ Three-Tier Hybrid Serverless Architecture

```mermaid
flowchart TD
    subgraph Client ["Client"]
        Browser[Next.js Modern Zen Web UI]
    end

    subgraph Vercel ["Vercel Edge (Seoul icn1)"]
        NextApp[Next.js 16 App Router]
        AuthCallback["/auth/callback client page"]
    end

    subgraph Supabase ["Supabase Cloud (Seoul ap-northeast-2)"]
        Auth[Supabase Auth - Google OAuth]
        DB[(PostgreSQL 16 + pgvector)]
        RLS[RLS and 50 welcome credits]
    end

    subgraph CloudRun ["Google Cloud Run (Seoul asia-northeast3)"]
        FastAPI[FastAPI backend container - non-root]
        JWTAuth[JWT verification and rate limiter]
        Engine[Zhu Xi changing-line rule engine]
        Pipeline[Multi-agent orchestration]
    end

    subgraph AI ["Google Cloud Vertex AI"]
        Gemini["Gemini 2.5 Flash<br/>thinking_budget=0 · 3s per turn"]
    end

    Browser -->|1. Google OAuth and session| Auth
    Browser -->|2. Page rendering| NextApp
    Browser -->|3. Counsel API with Bearer JWT| FastAPI
    FastAPI -->|4. Verify JWT and resolve user_id| JWTAuth
    FastAPI -->|5. Balanced search over 2,536 commentaries| DB
    FastAPI -->|6. 64-hexagram rule engine and agent inference| Gemini
    FastAPI -->>Browser: 7. Four-part report, reflective questions, live evidence
```

---

## 🤖 Multi-Agent Pipeline

```
[0] Safety Screener
    - Detects crisis signals in user input
    - On detection, skips hexagram derivation and routes to public hotlines (BLOCK_CRISIS)
    - 24-hour per-user latch (CRISIS_LATCH_HOURS) blocks circumvention
            | (on pass)
[1] Intake Agent
    - Clarifies the concern and classifies its category
    - Detects repeat questions (the jaesamdok / Meng hexagram principle) and carries the prior hexagram forward
            |
[2] Interpretation Agent
    - Derives six lines and changing lines via the rule engine (core.hexagram_engine)
    - Looks up verbatim hexagram and line statements per Zhu Xi's focus rule
    - Balanced RAG retrieval (core.rag) over Yichuan Yizhuan (1,752) and Zhouyi Benyi (784)
            |
[*] Report Agent (v4.1)
    - Fuses the question, six-line values, gobyeonjeom rules, Chinese source text, and RAG commentary
    - Writes the four-part report as structured JSON
            |
[3] Counsel Agent (five-turn Socratic coaching, v0.5.0)
    - Re-injects the stored report (report_data) into every turn's prompt to hold the interpretation steady
    - Five-stage coaching: theme, blind spot, prescription, future, action pledge
    - Hard five-turn guardrail (`is_final: true`) prevents endless loops
    - Four-gate critique-and-refinement loop suppresses clichés
            | (on completing five turns)
[*] Action Card Generator v2
    - Structures one concrete action pledge and renders a canvas graphic card
    - Supports encrypted card export
            |
[+1] Journal Agent
    - Records a conversation summary, core reflections, and action items to the database
```

---

## 🛡️ Zero-Trust Security & Engineering

| Area | Technique | Effect |
|---|---|---|
| **Authentication** | Supabase JWT signature verification (`PyJWT`, `HS256`, `aud="authenticated"`) | Blocks `user_id` forgery, crisis-latch bypass, and BOLA session hijacking |
| **Ledger concurrency** | Conditional atomic `UPDATE` (`credit_balance >= amount` + `RETURNING`) | Eliminates race conditions on credit deduction |
| **Inference latency** | Gemini 2.5 Flash `types.ThinkingConfig(thinking_budget=0)` | Per-turn latency **18s → 3s** |
| **Token diet** | Sliding conversation window (last 3 turns / 6 utterances) plus field compression | Cuts long-session token use by **over 50%** |
| **DoS and billing defense** | Sliding-window rate limiter (30 requests per minute per IP/user) with automatic memory cleanup | Blocks unauthorized calls and financial DoS |
| **Container hardening** | Non-root user (`appuser:1000`) and fixed entrypoint in the Dockerfile | Prevents container escape and root escalation |
| **Information disclosure** | OWASP security headers plus error stack-trace masking | Keeps infrastructure internals off the client |
| **Operational observability** | Structured JSON logging (`core/logging_config.py`) — an explicit `severity` field in production so Cloud Logging records the real level | Report status and `duration_ms` are traceable in logs. `httpx` and `google_genai` are raised to WARNING, suppressing ~20 request lines per consultation |
| **Health check** | `/health` runs `SELECT 1` against the database (3s timeout) | 200 with `database: ok` when healthy; 503 with `database: unavailable` on failure |

---

## 💻 Tech Stack

### Backend
- **Python 3.9+ / FastAPI** — async REST API (routers split into `api/routers/{counsel,card,safety}.py`)
- **Google Cloud Run** — stateless containers in Seoul (`asia-northeast3`), scale-to-zero 0–10
- **SQLAlchemy (asyncio) / asyncpg** — async PostgreSQL ORM with a cross-database `UUIDType`
- **Google GenAI / Vertex AI (Gemini 2.5 Flash)** — the multi-agent LLM pipeline
- **PyJWT** — Supabase JWT verification as an auth dependency

### Database & RAG
- **Supabase Cloud (PostgreSQL 16 + pgvector)** — Seoul (`ap-northeast-2`)
- **HNSW vector index** — 1,752 Yichuan Yizhuan + 784 Zhouyi Benyi = **2,536 commentary vectors**
- **Row Level Security** — SELECT-only grants and per-user data isolation

### Frontend
- **Next.js 16 (App Router, Turbopack)** — deployed to Vercel Seoul (`icn1`)
- **React 19 / TypeScript**
- **Tailwind CSS / Framer Motion / Lucide React**
- **Modern Zen UI** — six-line hexagram animation, four-part report viewer, five-turn Socratic chat, action-card modal renderer, live credit-balance badge

---

## 🚀 Getting Started

### 1. Environment

```bash
git clone https://github.com/casareborgia/IChing-AI-Consultant.git
cd IChing-AI-Consultant

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cd frontend
npm install
cd ..
```

### 2. Prompt Files (required)

Agent prompts (`prompts/*.md`) are **not** included in this repository. This repo is public and the prompts are not intended for publication, so they are excluded via `.gitignore`. **Without them the backend dies at import time with `FileNotFoundError`.**

If you have access, pull them from the private repository:

```bash
rm -rf prompts
git clone https://github.com/casareborgia/iching-prompts.git prompts
```

Without access you must author the nine files `core/prompts.py` expects: `counsel.md`, `duplicate_response.md`, `intake.md`, `interpret.md`, `journal.md`, `rag_translation.md`, `report.md`, `safety_response.md`, `safety_screening.md`. Each needs a `## 시스템 프롬프트` heading followed by a fenced code block — the loader reads only what is inside that fence (`core/prompts.py`).

### 3. Environment Variables (`.env`, `env.production.yaml`)

- Local development: copy from `.env.example`
- Production: copy `env.production.yaml.example` to `env.production.yaml` and fill in your GCP project ID and deployment domain

```env
# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/iching

# Gemini / Vertex AI
LLM_PROVIDER=gemini
GEMINI_MODEL=gemini-2.5-flash
GOOGLE_CLOUD_PROJECT=your-gcp-project-id

# Supabase JWT secret (for verification)
SUPABASE_JWT_SECRET=your-supabase-jwt-secret
```

### 4. Run the Backend

```bash
.venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8008 --reload
```

### 5. Run the Frontend

```bash
cd frontend
npm run dev
```

Open **`http://localhost:3000`** to start a consultation.

---

## 🧪 Tests & Benchmarks

The project ships 167 automated tests plus standard evaluation harnesses for Codex/CI verification:

```bash
# 1. Full unit and security integration suite (167 passed, 4 skipped)
.venv/bin/pytest -v

# 2. Credit race-condition and payment guard tests
.venv/bin/pytest tests/test_credit_system.py -v

# 3. Six core KPIs for the five-turn Socratic counsel
.venv/bin/python scripts/evaluate_counsel_kpi.py --mock --json

# 4. JWT authentication and BOLA defense
.venv/bin/pytest tests/test_jwt_auth.py -v

# 5. Safety screening benchmark (115 cases)
.venv/bin/python scripts/score_safety.py -p gemini
```

> **Evaluation guide**: quantitative audit criteria and the scoring rubric live in [`docs/PROJECT_EVALUATION_KPI.md`](docs/PROJECT_EVALUATION_KPI.md).

---

## 📄 License & Disclaimers

- This service is not a medical device (SaMD) and does not replace professional psychotherapy. It is a wellness AI tool for self-reflection and decision support.
- In a crisis, Korea's 24-hour suicide prevention line (`109`) and mental-health crisis line (`1577-0199`) are available.

### License (code and data differ)

| Subject | License | File |
|---|---|---|
| Source code | **MIT License** — free use, modification, and redistribution | [`LICENSE`](LICENSE) |
| `data/` text and derivatives | **CC BY-SA 4.0** — attribution and share-alike | [`data/PROVENANCE.md`](data/PROVENANCE.md) |

Source code may be used freely under the MIT License; the dataset and source materials follow CC BY-SA 4.0 attribution terms.
