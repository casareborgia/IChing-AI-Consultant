# 3단계 작업 지시서 — 괘사·효사 한글 번역

이 문서는 3단계를 맡는 사람/에이전트가 먼저 읽는다.
`CLAUDE.md`의 설계 원칙이 상위 문서이고, 충돌하면 `CLAUDE.md`가 이긴다.

---

## 1. 번역 대상은 450건이다

`CLAUDE.md`에는 384건으로 적혀 있으나 실제 데이터 기준으로는 다르다.

| 원문 | 건수 | 저장 컬럼 | 3단계 대상 |
|---|---|---|---|
| 괘사 | 64 | `hexagrams.judgment_ko` | ✅ |
| 효사 | 386 | `lines.statement_ko` | ✅ |
| 소상전 | 386 | 컬럼 없음 | ❌ 4단계 RAG로 |
| 단전 | 64 | 컬럼 없음 | ❌ 4단계 RAG로 |
| 대상전 | 64 | 컬럼 없음 | ❌ 4단계 RAG로 |
| 문언전 | 2 (건·곤) | 컬럼 없음 | ❌ 4단계 RAG로 |

**합계 450건** (효사가 384가 아니라 386인 것은 건괘 用九·곤괘 用六 때문).

소상전·단전을 빼는 근거는 취향이 아니다. **2단계 엔진의 `focus_rule`이 가리키는
대상은 괘사와 효사뿐**이다(`core/hexagram_engine.py`의 `calculate_focus_rule` 참조).
소상전 이하는 해석의 근거 자료이므로 4단계 RAG 청크로 가는 것이 데이터 레이어
구분에 맞다.

**스키마를 늘리지 말 것.** 소상전 번역 컬럼이 필요하다고 판단되면 코드를 고치기 전에
사람에게 물어본다.

---

## 2. 작업 순서와 멈춰야 할 지점

```
A. 준비          ← 에이전트
B. 파일럿 실행    ← 에이전트
──────────── 사람 판단 게이트 ────────────
C. 모델·용어표 확정 ← 사람만
──────────────────────────────────────
D. 450건 배치     ← 에이전트
E. 적재와 검증    ← 에이전트
```

**C를 에이전트가 대신 결정하면 안 된다.** 파일럿 채점은 사람이 블라인드로 한다.
"제가 보기엔 A가 낫습니다"로 넘어가지 말고, 채점지를 만들어 놓고 멈춘다.

---

## A0. 환경 — 2026-08-14 실측

호출 경로는 **Vertex AI 단일 경로**로 확정했다. Gemini와 Claude 둘 다 Vertex로 부른다.
인증이 ADC 하나로 끝나고, 실행 조건(temperature 등)을 두 모델에 같은 방식으로
먹일 수 있어 비교 오염이 줄어든다. Anthropic API 직접 호출은 쓰지 않는다.

확인된 것:

| 항목 | 상태 |
|---|---|
| 번역 대상 450건 | `data/hexagrams.json` 실측 일치 (괘사 64 + 효 386) |
| `judgment_ko`·`statement_ko` 컬럼 | 이미 있음 → **마이그레이션 불필요** |
| GCP 프로젝트 | `southern-engine-495314-p2` |
| ADC | 있음 + quota project 설정 완료 |
| Vertex AI API | 활성화 완료 (`aiplatform.googleapis.com`) |
| Gemini | ✅ `gemini-2.5-pro` / `us-central1` 호출 성공 확인 |
| Claude | ❌ 404 — Model Garden 사용 신청 전 |

**남은 것 — 이게 안 되면 B를 시작할 수 없다:**

Model Garden에서 **Claude 모델 사용 신청/약관 동의**를 사람이 해야 한다.
에이전트가 대신 누르지 않는다. 신청 전에는 `anthropic` 퍼블리셔 모델이 전부 404다.

리전·모델 ID 실측 (2026-08-14, 이 프로젝트 기준):

- `gemini-2.5-pro` @ `us-central1` — 200
- `gemini-3-pro`, `gemini-3-pro-preview`, `gemini-3-flash` — 404 (이 프로젝트엔 없다)
- Claude는 Vertex 승인 전이라 파일럿을 **Anthropic Direct API**로 돌렸다.
  Vertex 단일 경로 결정에서 벗어난 것이므로, D단계 경로를 정할 때 다시 판단할 것.

Claude on Vertex 실측 (Model Garden 사용 설정 완료 후):

| 리전 | 응답 | 뜻 |
|---|---|---|
| `global` | 429 | 서빙됨. 할당량 0 |
| `us-east5` | 429 | 서빙됨. 할당량 0 |
| `us-central1` | 400 | **이 리전에서는 서빙 안 됨** (Gemini와 같은 리전을 못 쓴다) |
| `europe-west1` | 404 | 없음 |

Vertex 모델 ID는 `claude-sonnet-4-5@20250929` (`@` 구분자). Direct API의
`claude-sonnet-4-5-20250929`와 같은 모델이나 표기가 다르다.

호출하려면 할당량 상향을 신청해야 한다. 걸리는 항목:
`aiplatform.googleapis.com/global_online_prediction_requests_per_base_model`
(base model `anthropic-claude-sonnet-4-5`)

파일럿에 실제로 쓴 조건 (`pilot/runs/`):

| 팔 | 모델 | 경로 | 출력 상한 |
|---|---|---|---|
| Gemini | `gemini-2.5-pro` | Vertex `us-central1` | 8192 |
| Claude | `claude-sonnet-4-5-20250929` | Anthropic Direct API | 2048 |

출력 상한이 다르지만 Claude 쪽 실측 최장 번역이 105자라 잘린 항목은 없다.
채점에는 영향이 없다. 이후 실행은 `MAX_OUTPUT_TOKENS`로 양쪽 8192 통일이다.

**Claude를 Direct API로 450건 돌릴 때 주의.** 이 `ANTHROPIC_API_KEY`는 사용자의
다른 에이전트들이 함께 쓰고 있다. `--concurrency`를 올려 배치를 돌리면 그쪽이
같이 느려지거나 한도에 걸린다. Vertex로 옮기면 GCP 할당량으로 분리된다.

에이전트가 걸릴 함정:

- `gcloud`가 venv의 Python 3.9로 뜨면 로드 자체가 실패한다.
  `CLOUDSDK_PYTHON=/opt/homebrew/bin/python3.11`을 걸고 쓴다. (Python SDK 호출은 3.9로 정상)
- `core/config.py`의 `Settings`는 `extra="ignore"`다. `.env`에 `GOOGLE_CLOUD_PROJECT`를
  넣기만 하면 **읽히지 않는다.** 필드를 추가해야 한다.
- **리전이 모델마다 다르다.** Claude는 서빙 리전이 한정돼 있어 Gemini와 같은 리전을
  쓰지 못할 수 있다. location을 전역 상수 하나로 두지 말고 모델별로 잡는다.
- 모델 ID는 API를 켠 뒤 `gcloud ai model-garden models list`로 **실제 목록을 보고 고정한다.**
  짐작으로 쓰지 말 것. 고정한 ID를 `runs/*.json`에 같이 적어 둔다 —
  나중에 450건을 어느 모델로 돌렸는지 대조할 근거가 된다.

## A. 준비

1. `main`에서 브랜치를 딴다: `feature/step3-translation`
2. `pilot/items.json`이 없으면 `python pilot/build_items.py`로 만든다.
3. 번역 호출 스크립트 `scripts/translate.py`를 만든다. 요건:
   - `pilot/PROMPT.md`의 시스템 프롬프트를 **그대로** 쓴다. 모델별로 손보지 않는다.
   - 1건 1호출, 대화 이력 없음, temperature 0
   - 출력은 JSON 배열로 파일 저장. **DB에 직접 쓰지 않는다.**
   - 실패·재시도·부분 저장을 견딜 것. 450건 도중에 끊겨도 이어서 돌 수 있어야 한다.

4. 의존성을 추가한다. `requirements.txt`에 Vertex 호출용 SDK가 아직 없다.
   `core/config.py`에 `GOOGLE_CLOUD_PROJECT` 등 필드를 넣고 `.env.example`도 같이 갱신한다
   (실값은 `.env`에만, `.env`는 gitignore 대상이다).

호출은 A0대로 Vertex AI를 직접 쓴다. **Antigravity 내장 에이전트 크레딧으로 450건을 돌리지 말 것**
(월 한도가 거의 소진된 상태다).

## B. 파일럿 실행

`pilot/PROMPT.md`의 실행 조건대로 12건을 돌린다.

- 모델 2종 × 2회 = 4벌, `pilot/runs/{모델}-{회차}.json`
- 끝나면 `python pilot/compare.py pilot/runs/A-1.json pilot/runs/B-1.json`
- 생성된 `pilot/blind_sheet.md`를 사람에게 넘기고 **멈춘다**

## C. 사람 판단 게이트

사람이 `pilot/RUBRIC.md`로 블라인드 채점 후 두 가지를 정한다.

1. **어느 모델로 450건을 돌릴지** (또는 둘 다 돌릴지)
2. **용어표 확정본** — 파일럿의 `key_terms` 출력을 모아 사람이 승인한다.
   이게 386건 일관성의 뼈대다.

## D. 450건 배치

확정된 모델·용어표로 돌린다. 출력은 `data/translations/{모델}.json`.

**두 모델을 다 돌렸다면** 번역이 갈리는 항목을 뽑아 `data/translations/diff.md`로
정리한다. 그 목록이 사람이 검수할 대상이다.

## E. 적재와 검증

1. 적재 스크립트 `scripts/load_translations.py`
   - `scripts/seed_hexagrams.py`의 방식을 따른다(존재하면 갱신, 없으면 삽입 = 멱등)
   - `judgment_ko`, `statement_ko`만 채운다
2. 검증 테스트를 `tests/`에 추가한다. 최소 세 가지:
   - 450건이 빠짐없이 채워졌는가 (NULL 0건)
   - 원문(`*_text`)이 단 한 글자도 변하지 않았는가
   - 용어표의 핵심어가 번역문에서 일관되게 쓰였는가

---

## 하지 말 것

1. **원문을 고치지 마라.** `judgment_text`, `statement_text`, `small_xiang_text`,
   `data/hexagrams.json`의 원문 필드는 읽기 전용이다.
   현토가 빠져 보이는 곳이 있으나(예: 29괘 `有孚야`, 29-2 `求` 뒤 공백)
   **원본 사이트가 그렇게 되어 있는 것을 확인했다.** 복원하지 마라.
2. **번역을 상담체로 각색하지 마라.** 이 번역은 사용자에게 보이는 글이 아니라
   해석 단계가 참조하는 근거 자료다. 각색은 `agents/counsel`의 일이다.
3. **파일럿을 건너뛰고 450건을 돌리지 마라.**
4. **모델 선택을 대신 결정하지 마라.**

## 커밋 전 점검

오늘까지의 작업에서 실제로 나온 문제들이다. 같은 것을 반복하지 않는다.

- [ ] `git status`에 미추적 파일이 없는가 (전에 데모 스크립트가 커밋에서 빠졌다)
- [ ] 테스트가 **실패할 줄 아는가**. 일부러 틀린 값을 넣어 실패를 확인했는가
- [ ] 새 코드가 원문 데이터를 건드리지 않았는가
- [ ] `CLAUDE.md`의 작업 순서 체크박스를 갱신했는가

## 참고

- 원문 파싱은 외부 정답과 대조해 검증되어 있다(29괘 15개 필드 전부 일치).
  파서를 의심하기 전에 이 사실을 먼저 고려한다.
- 번역 검수 시 기존 학술 국역(성백효 역주 『주역전의』 등)을 **눈으로 대조하는
  참고용으로만** 쓴다. RAG에 넣거나 복제하면 저작권 문제이며,
  `CLAUDE.md`의 법적 확인 목록에 걸린다.
