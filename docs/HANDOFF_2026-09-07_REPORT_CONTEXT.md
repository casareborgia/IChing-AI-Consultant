# 리포트 컨텍스트 개선 작업 인계 (2026-09-07)

## 목적

정상 리포트가 생성된 뒤에도 후속 상담에서 같은 해석 기준을 유지하고, 리포트 실패와 지연을 운영에서 확인할 수 있게 한다. 프런트엔드의 고정 해석 폴백과 프롬프트 예시 어휘 오염 가능성도 제거한다.

## 완료한 작업

### 1. 리포트 컨텍스트 영속화

- `counsel_sessions`에 다음 필드를 추가했다.
  - `report_data` JSONB
  - `report_status` VARCHAR(20), 기본값 `not_requested`
  - `report_error_code` VARCHAR(50)
- 마이그레이션: `migrations/versions/d7f4a1c2e8b9_persist_report_context.py`
- 첫 리포트 생성 성공 시 세션에 전체 리포트를 저장한다.
- 실패 시 `report_status=failed`와 예외 타입을 `report_error_code`에 저장한다.
- 후속 턴에서 `c_session.report_data`를 `run_counsel_turn()`에 다시 전달한다.
- API 시작/후속 턴 응답에 `report_data`, `report_status`, `report_error_code`를 포함한다.

### 2. 운영 관측성

- 리포트 생성마다 다음 구조의 로그를 남긴다.
  - 세션 ID
  - `ready`/`failed` 상태
  - 생성 소요 시간 `duration_ms`
- 실패 로그에 `error_code`를 포함한다.
- `/health`가 DB에 `SELECT 1`을 실행한다.
  - 정상: HTTP 200, `database: ok`
  - DB 실패/3초 초과: HTTP 503, `database: unavailable`

### 3. 프런트엔드 폴백 제거

- `HexagramReportView.tsx` 내부에 남아 있던 고정 해석 문장 전체를 제거했다.
- `reportData`가 없으면 기존의 명시적 오류 화면만 표시한다.
- 새 상담 시작 시 `reportData`를 `undefined`로 초기화한다.
- API 타입에 `reportStatus`, `reportErrorCode`를 추가했다.

### 4. 프롬프트 오염 가능성 제거

- `prompts/report.md`와 `agents/report.py`에서 다음을 제거했다.
  - 특정 비즈니스 금지어 목록
  - 구체적 도메인별 완성형 어휘 예시
  - 주역 상징 예시 목록
  - 반복 상투구의 완성형 예문
- 사용자 질문과 `topic_category`에서만 어휘·톤·프레임을 도출하도록 추상 규칙으로 변경했다.
- 고변점, 변효 수에 따른 본괘/지괘 선택, 괘사·효사 DB 조회 로직은 변경하지 않았다.
- A/B 하네스 `scripts/compare_report_prompt_priming.py`는 과거 예시 프롬프트와 현재 zero-shot 프롬프트를 비교하도록 갱신했다.

### 5. 기타 수정

- 화면 문구의 `재삼덕` 오타를 `재삼독`으로 수정했다.
- URL 인코딩된 DB 비밀번호의 `%` 때문에 Alembic이 실행되지 않던 문제를 수정했다.
  - `migrations/env.py`에서 ConfigParser 전달 시 `%`를 `%%`로 이스케이프한다.
- 후속 턴 프롬프트에 저장된 리포트 행동 지침과 최종 요약이 실제 포함되는 회귀 테스트를 추가했다.

## 검증 결과

- 전체 백엔드: `161 passed, 4 skipped`
- 관련 통합 테스트: `48 passed`
- 프런트엔드: `next build --webpack` 성공, TypeScript 성공
- Vercel 운영 빌드의 Turbopack/TypeScript/정적 페이지 생성 성공
- 프롬프트 A/B 하네스 치환 로직 로컬 확인 완료
- 로컬 Alembic `d7f4a1c2e8b9` 적용 성공

## 운영 DB 작업

운영 DB에는 기존 테이블이 있었지만 `alembic_version`이 없었다. 초기 마이그레이션을 실행하면 `counsel_sessions already exists`로 실패했다. 현재 서비스가 `contextual_mapping`, `evidence_items`를 이미 사용하고 있으므로 다음 순서로 처리했다.

1. Cloud Run Job `iching-db-migrate` 생성
2. 기존 스키마 기준점을 `b41d7e6a2f95`로 stamp
   - 실행 `iching-db-migrate-45hbq` 성공
3. `alembic upgrade head` 실행
   - 실행 `iching-db-migrate-lshk4` 성공

운영 DB URL은 Secret Manager의 `database-url`을 사용하며 값 자체를 출력하지 않는다.

## 배포 상태

### 백엔드

- GCP 프로젝트: `southern-engine-495314-p2`
- 리전: `asia-northeast3`
- 서비스: `iching-counsel-api`
- 이미지 태그: `asia-northeast3-docker.pkg.dev/southern-engine-495314-p2/cloud-run-source-deploy/iching-counsel-api:report-context-20260907`
- 이미지 digest: `sha256:5abcfc7f30ae57b6b7bfe099442247e340319841304b98033e4a49ae60ce634d`
- 현재 리비전: `iching-counsel-api-00030-cvd`
- 트래픽: 100%
- URL: `https://iching-counsel-api-517419857386.asia-northeast3.run.app`

### 프런트엔드

- Vercel 배포 ID: `dpl_3LoTUah28gDtMi8sukARaGR3QU8v`
- 배포 URL: `https://i-ching-ai-consultant-ja8gtn9hh-casareborgias-projects.vercel.app`
- 운영 alias: `https://i-ching-ai-consultant.vercel.app`
- 상태: READY

### Git

- 로컬 커밋: `e639f65 Persist report context across counsel turns`
- 브랜치: `main`
- 이 인계 문서는 위 커밋 이후 생성했다.

## 남은 작업

중단 직전 아래 최종 검증은 아직 실행하지 못했다. 반드시 순서대로 확인한다.

1. 새 백엔드 헬스 체크

   ```bash
   curl -i https://iching-counsel-api-517419857386.asia-northeast3.run.app/health
   ```

   기대값: HTTP 200과 `"database":"ok"`.

2. 최신 리비전 로그 확인

   ```bash
   gcloud logging read \
     'resource.type="cloud_run_revision" AND resource.labels.revision_name="iching-counsel-api-00030-cvd"' \
     --project southern-engine-495314-p2 --limit 100
   ```

   확인 항목: startup 오류, DB 컬럼 오류, 5xx, `리포트 에이전트 실행 실패`.

3. 운영 DB Alembic 버전 재확인

   Cloud Run Job `iching-db-migrate`의 command를 `alembic`, args를 `current`로 바꿔 실행하고 로그에서 `d7f4a1c2e8b9 (head)`를 확인한다. 확인 후 Job을 `upgrade head` 상태로 되돌려도 된다.

4. 운영 프런트 번들 확인

   운영 페이지의 JS chunk를 받아 다음 문자열이 없는지 확인한다.
   - `타당성 객관 검증`
   - `안정적 연착륙`
   - `승리의 열쇠`
   - `기류 속에 있습니다`

5. 실제 로그인 세션 E2E

   - 신규 상담 시작
   - 리포트 정상 표시 확인
   - 같은 세션에서 2턴째 메시지 전송
   - Cloud Run 로그에서 첫 턴 `report_status=ready`와 `duration_ms` 확인
   - DB의 해당 `counsel_sessions.report_data`가 비어 있지 않은지 확인
   - 2턴 상담이 첫 리포트의 행동 지침·최종 요약과 충돌하지 않는지 확인

6. 원격 Git 반영

   로컬 커밋 `e639f65`는 아직 원격 push 여부를 확인하지 못했다. `git status -sb`, `git log -1`, `git remote -v`를 확인한 뒤 필요하면 push한다. 이 인계 문서도 별도 커밋에 포함한다.

7. 서비스 모델 프롬프트 회귀 측정

   코드·배포 검증이 끝난 뒤 별도 변수로 실행한다.

   ```bash
   python scripts/compare_report_prompt_priming.py -p gemini -n 2
   ```

   과거 예시 프롬프트와 현재 zero-shot 프롬프트 각각 가족 질문 6회 결과의 도메인 누출 여부를 비교한다. 서비스 호출 비용이 발생한다.

## 판단을 보류한 항목

- 리포트 실패 시 크레딧 자동 환불은 적용하지 않았다. 상담 답변 자체는 제공되므로 상품 정책 결정이 필요하다.
- 리포트 정제 루프는 유지했다. 최근 시작 요청은 약 4.4~33.3초로 편차가 컸다. 새 `duration_ms` 로그를 모은 뒤 정제 루프의 품질 개선량과 비용·지연을 비교해 결정한다.
- 기존 세션에는 `report_data`가 없으므로 후속 턴에서 기존 괘 근거만 사용한다. 새 배포 이후 생성된 세션부터 리포트가 복원된다.

## 주의사항

- 운영 DB 마이그레이션은 서비스 배포 전에 이미 완료됐다. 같은 migration을 수동 SQL로 다시 적용하지 않는다.
- 새 코드는 DB 컬럼에 의존하므로 운영 DB를 이전 revision으로 downgrade하지 않는다.
- 프롬프트를 다시 수정할 때 클라이언트 설정이나 모델을 동시에 바꾸지 않는다.
- `prompts/report.md`는 기존 ignore 규칙에 걸려 `git add -f`로 처음 추적했다. **이 조치는 이후 되돌렸다.** 공개 저장소에 노출되어 히스토리에서 제거했다(아래 "공개 히스토리 정리" 절). 지금은 나머지 프롬프트와 같이 추적하지 않는다.

## 검증 실행 결과 (2026-09-07 추가)

위 "남은 작업" 7개 항목 중 5번(실제 로그인 E2E)을 제외한 전 항목을 실행했다.

### 1. 백엔드 헬스 체크 — 통과

`HTTP/2 200`, 본문 `{"status":"ok","service":"iching-oracle-api","env":"production","database":"ok"}`.

### 2. 최신 리비전 로그 — 통과

- 서비스 `iching-counsel-api`의 최신 준비 리비전과 트래픽 100% 리비전이 모두 `iching-counsel-api-00030-cvd`.
- 이미지 태그 `report-context-20260907` 확인.
- `severity>=WARNING` 로그 0건.
- startup 정상: `Started server process [1]` → `Application startup complete` → `Uvicorn running on http://0.0.0.0:8080`, STARTUP TCP probe 1회 성공.
- DB 컬럼 오류, 5xx, `리포트 에이전트 실행 실패` 없음.
- 단, 배포 이후 상담 트래픽이 아직 없어 `리포트 생성 완료` 로그도 아직 없다. 이는 5번 E2E에서 확인해야 한다.

### 3. 운영 DB Alembic 버전 — 통과 (대체 확인)

`gcloud run jobs execute --args=current` 실행은 이 환경의 권한 정책에 막혀 수행하지 못했다. 대신 기존 Job 실행 로그로 확인했다.

- 실행 `iching-db-migrate-lshk4`: `Running upgrade b41d7e6a2f95 -> d7f4a1c2e8b9, persist report context on counsel sessions` 후 `Container called exit(0)`.
- 로컬 리비전 그래프상 `d7f4a1c2e8b9`를 `down_revision`으로 참조하는 리비전이 없으므로 head가 맞다.

### 4. 운영 프런트 번들 — 통과

운영 페이지가 참조하는 JS chunk 9개(약 1.0MB)를 받아 검사했다.

- `타당성 객관 검증` 0건
- `안정적 연착륙` 0건
- `승리의 열쇠` 0건
- `기류 속에 있습니다` 0건
- `재삼덕` 오타 0건

같은 번들에서 `맞춤 해석 리포트를 불러오지 못했습니다`, `마크다운 전문 복사`, `도출된 지괘` 등 `HexagramReportView` 문자열이 검출되므로, 대상 컴포넌트가 실제로 포함된 상태에서의 0건이다.

### 5. 실제 로그인 세션 E2E — 미실행

계정 로그인과 크레딧 차감이 필요해 보류했다. 확인해야 할 로그 패턴은 다음과 같다.

- 성공: `리포트 생성 완료: session=<sid> status=ready duration_ms=<n>`
- 실패: `리포트 에이전트 실행 실패: session=<sid> error_code=<type>`

### 6. 원격 Git 반영 — 완료

`origin/main`을 `ee8c782`에서 `c033547`으로 갱신했다. 운영 배포 코드와 원격이 일치한다.

### 7. 프롬프트 회귀 측정 — 실행 완료, 회귀 없음

`python scripts/compare_report_prompt_priming.py -p gemini -n 2`

- 결과 요약: `{"legacy_examples": 0, "current_zero_shot": 0}` (질문 3종 × 2회 × 2군 = 12회)
- 출력 분량: legacy 평균 2,039자(1,870~2,279), zero-shot 평균 1,962자(1,775~2,319). 품질 저하나 빈 응답 없음. 괘사·효사 한문 원문, 고변점 규칙 설명, 체용 관계 서술 모두 정상 생성.
- 해석: zero-shot 프롬프트에 **회귀는 없다**. 다만 legacy 군에서도 누출이 0이라 이번 표본으로는 "예시 어휘가 오염을 유발한다"는 가설을 검증도 반증도 하지 못했다.
- 이 하네스로 가설을 실제로 검정하려면 다음이 필요하다.
  - 표본 확대 (군당 6회는 부족)
  - `temperature=0.1` 고정 해제
  - 경계 사례 질문 추가 (예: 가족 문제인데 금전·계약 어휘가 섞인 질문)
- 원본 데이터: `/tmp/report_prompt_priming.json`

### 백엔드 테스트 재실행

`161 passed, 4 skipped` — 인계 문서 기재값과 동일.

주의: 이 저장소는 `prompts/*.md`를 전부 gitignore한다(`prompts/.gitkeep`만 추적). 새 worktree에서 테스트를 돌리려면 프롬프트 9개와 `.env`를 메인 체크아웃에서 복사해야 한다.

## 로깅 결함 발견 및 수정 (2026-09-07)

### 문제

위 "완료한 작업 / 2. 운영 관측성"은 실제로 동작하지 않았다. 배포 후 상담 한 사이클(start 1회 + turn 5회, 전부 200)을 돌렸는데 `리포트 생성 완료` 로그가 한 줄도 남지 않았다.

원인은 root 로거에 핸들러가 없었던 것이다. `uvicorn api.main:app`으로 띄우면 uvicorn은 자기 로거("uvicorn", "uvicorn.error", "uvicorn.access")만 설정하고 root는 건드리지 않는다. root에 핸들러가 없으면 파이썬은 lastResort 핸들러(WARNING 이상, stderr)로만 내보낸다. 저장소 어디에도 `logging.basicConfig()`나 `dictConfig()` 호출이 없었다.

결과적으로 다음과 같이 갈렸다.

- `리포트 생성 완료: ... status=... duration_ms=...` — `logger.info` → 전량 유실
- `리포트 에이전트 실행 실패: ... error_code=...` — `logger.error` → lastResort로 출력

실패는 보이는데 성공과 소요 시간이 보이지 않는 상태였다. 보류 항목이던 "정제 루프 유지 여부를 `duration_ms` 로그를 모아 판단한다"도 데이터가 쌓이지 않아 불가능했다.

### 수정

- `core/logging_config.py` 추가. 앱 임포트 시점에 `dictConfig`로 root에 핸들러를 붙인다.
- `api/main.py`에서 라우터·에이전트를 임포트하기 전에 `configure_logging()`을 호출한다.
- `core/config.py`에 `LOG_LEVEL`을 추가했다. 기본 `INFO`, 인식할 수 없는 값이면 `INFO`로 폴백한다.
- Cloud Run은 stdout을 INFO, stderr를 ERROR로 뭉뚱그린다. 그래서 운영에서는 `severity` 필드를 담은 JSON 한 줄로 내보내 Cloud Logging이 실제 레벨을 읽게 했다. 로컬은 평문을 유지한다.
- `disable_existing_loggers`는 False다. True면 먼저 만들어진 uvicorn 로거가 꺼져 액세스 로그가 사라진다.
- root에 핸들러를 붙이면 서드파티 로거도 함께 흘러나온다. `httpx`, `httpcore`, `google_genai`는 LLM·임베딩 호출마다 요청 URL을 INFO로 남겨 상담 1건에 20줄 넘게 쌓였다. 이 셋만 WARNING으로 올렸다. 호출 실패는 WARNING 이상이라 그대로 보인다.
- 회귀 테스트 `tests/test_logging_config.py` 6개를 추가했다.

### 검증

- 전체 백엔드: `167 passed, 4 skipped`
- uvicorn `LOGGING_CONFIG`를 먼저 적용한 뒤 앱을 임포트하는 실제 기동 순서를 재현해, 앱 로그가 JSON으로 나오고 uvicorn 액세스 로그가 중복 없이 한 줄만 나오는 것을 확인했다.
- 운영 확인: 서명이 틀린 JWT로 401 경로를 태워 다음을 얻었다. `severity>=WARNING` 조회에 걸리므로 Cloud Logging이 JSON을 파싱해 실제 레벨을 붙인 것이 확인된다.

  ```
  WARNING  iching_auth  HS256 JWT 서명 검증 실패: InvalidSignatureError
  ```

### 남은 작업 5번(실제 로그인 E2E) 완료

로깅 수정 배포 후 상담 한 사이클을 더 돌려 확인했다.

```
15:53:36  start 시작
15:53:41  임베딩 (RAG)
15:54:04  리포트 생성 완료: session=447e9a7e-... status=ready duration_ms=17754
15:54:06  POST /api/counsel/start  200   (총 약 30초)
15:56:39  POST /api/counsel/turn   200   (약 3.6초)
15:57:29  POST /api/counsel/turn   200   (약 4.5초)
15:58:18  POST /api/counsel/turn   200   (약 4.9초)
15:58:58  POST /api/counsel/turn   200   (약 7.4초)
```

`status=ready`는 `report_data` 저장의 직접 증거다. `agents/pipeline.py`에서 `report_status = "ready"`는 `c_session.report_data = report_data` 바로 뒤에서만 설정되기 때문이다. `리포트 에이전트 실행 실패`도 5xx도 없었다.

`duration_ms` 첫 실측값은 17,754ms다. 표본 1개이고 이전 관측 편차가 4.4~33.3초였으므로, 정제 루프 유지 여부는 더 모은 뒤 판단한다.

### 배포

- 이미지 태그: `asia-northeast3-docker.pkg.dev/southern-engine-495314-p2/cloud-run-source-deploy/iching-counsel-api:logging-config-20260907`
- 이미지 digest: `sha256:0ed4936c8a846f6deee1af7aa182cfdb086c14b1252fcfff318d75e122896daf`
- 리비전: `iching-counsel-api-00031-kt8`, 트래픽 100%
- 기존 서비스 설정(서비스 계정, timeout 300s, concurrency 80, 1 CPU / 1Gi, env var 8개)은 그대로 유지됐다.
- 헬스 체크: HTTP 200, `database: ok`

서드파티 로거를 조용히 시킨 변경은 이 배포 이후 별도 이미지로 나간다.

## 로그 소음 감소 배포 및 검증 (2026-09-07)

### 배포

- 이미지 태그: `asia-northeast3-docker.pkg.dev/southern-engine-495314-p2/cloud-run-source-deploy/iching-counsel-api:log-noise-20260907`
- 이미지 digest: `sha256:69b4fd663abeef2a561efc2110f5fb4e8d5b734a571080400d4e82ac3a119f4c`
- 리비전: `iching-counsel-api-00032-r6f`, 트래픽 100%
- env var 8개 유지, 기동 정상, 헬스 체크 HTTP 200 / `database: ok`

배포 직후 서명이 틀린 JWT로 401 경로를 태워, 서드파티를 조용히 시키면서 앱 로거까지 막지는 않았음을 먼저 확인했다.

```
WARNING  iching_auth  HS256 JWT 서명 검증 실패: InvalidSignatureError
```

### 검증 결과

배포 후 상담 한 사이클(16:19:17~16:24:26)을 돌려 로거별 줄 수를 셌다.

| 로거 | 수정 전 사이클 | 수정 후 사이클 | 판정 |
| --- | --- | --- | --- |
| `httpx` INFO | 12줄 | 0줄 | 통과 |
| `httpcore` INFO | — | 0줄 | 통과 |
| `google_genai.models` INFO | 10줄 | 0줄 | 통과 |
| `agents.pipeline` INFO | 1줄 | 1줄 | 유지 |

마지막 행이 핵심이다. 서드파티를 줄이면서 정작 필요한 줄까지 사라지면 실패인데, 그대로 남았다.

```
16:19:39  INFO  agents.pipeline
리포트 생성 완료: session=2e0be535-54c6-447a-b903-19433405bea1 status=ready duration_ms=11906
```

사이클 전체도 정상이다. `POST /api/counsel/start` 200(16:19:42), `POST /api/counsel/turn` 200 4회(16:21:45 / 16:22:16 / 16:23:33 / 16:24:26). 5xx 없음, `리포트 에이전트 실행 실패` 없음.

### 남겨둔 것

- `google_genai.models`가 사이클당 남기는 AFC 권고 메시지 1줄은 그대로 둔다. 원래 WARNING 레벨이라 필터를 통과하며, SDK 사용법에 대한 실제 경고이므로 지우면 손해다.
- 로거별 줄 수를 셀 때는 최상위 `severity` 필드를 쓴다. Cloud Logging이 JSON의 `severity` 키를 엔트리 필드로 올리므로 `jsonPayload.severity`로 조회하면 아무것도 걸리지 않는다.

  ```bash
  gcloud logging read \
    'resource.type="cloud_run_revision" AND resource.labels.revision_name="<리비전>" AND jsonPayload.logger="agents.pipeline" AND severity="INFO"' \
    --project southern-engine-495314-p2
  ```

- 루트 경로 `GET /` 404가 간헐적으로 찍힌다. 핸들러가 없어서 나는 정상 동작이고 이번 작업과 무관하다.

### duration_ms 누적

| 시각 | 세션 | duration_ms |
| --- | --- | --- |
| 15:54:04 | `447e9a7e` | 17,754 |
| 16:19:39 | `2e0be535` | 11,906 |

표본 2개다. 이전 관측 편차가 4.4~33.3초였으므로 정제 루프 유지 여부는 실사용이 붙은 뒤 판단한다. 이제 로그가 쌓이므로 위 조회로 모을 수 있다.

## 공개 히스토리 정리 (2026-09-07)

### 발견

이 저장소는 `visibility: PUBLIC`이다. 그런데 `.gitignore`가 "공개 대상이 아닌 것"으로 분류한 파일들이 히스토리에 그대로 남아 있었다. 과거의 `6fa4b66`, `88a0bf6` 같은 커밋이 "Git 추적 해제"를 했지만 추적만 끊고 히스토리는 남겼기 때문이다. 여기에 `prompts/report.md`가 `e639f65`에서 `git add -f`로 새로 추가되며 현재 트리에도 올라갔다.

제거 대상은 19개 경로였다.

- `prompts/` 9개 전부
- `AGENTS.md`, `frontend/AGENTS.md` (내부 실측·원가·약점 분석)
- `CLAUDE.md`, `frontend/CLAUDE.md` (측정 방법론·비용 수치·약점 목록)
- `docs/DEPLOYMENT_AND_MONETIZATION_BLUEPRINT.md` (가격·원가·마진)
- `docs/STEP5_INSTRUCTIONS.md`
- `pilot/HANDOFF.md`, `pilot/PROMPT.md`, `pilot/RUBRIC.md`
- `env.production.yaml`

`env.production.yaml`은 모든 버전을 검사했고 자격증명이 없었다. 키가 `ENVIRONMENT`, `LLM_PROVIDER`, `GOOGLE_CLOUD_PROJECT`, `GEMINI_MODEL`, `CORS_ORIGINS`, `CRISIS_LATCH_HOURS` 6개뿐이며, DB 비밀번호와 JWT 시크릿은 처음부터 Secret Manager를 썼다. **자격증명 유출은 없었다.**

### 조치

1. `--mirror` 클론 후 재작성 전 전체를 번들로 백업했다.
2. `git filter-repo --invert-paths`로 19개 경로를 전체 히스토리에서 제거했다. 248개 커밋을 재작성했다.
3. 브랜치 7개와 태그 2개를 force push했다. `refs/pull/*`는 GitHub이 읽기 전용으로 관리하므로 대상에서 제외했다.

검증 결과 제거 대상 외 파일 목록은 재작성 전후가 동일했다(314개). `prompts/.gitkeep`은 보존되어 디렉터리 구조가 유지된다.

### 남은 노출

**히스토리 재작성으로 완전 삭제가 되지는 않았다.** 옛 커밋 SHA로 직접 접근하면 아직 읽힌다.

```
현재 main 경로            404  (제거 완료)
b949a7b/prompts/report.md 200  ← 아직 읽힘
e639f65 이전 SHA          200  ← 아직 읽힘
```

원인은 두 가지다.

- GitHub은 unreachable 객체를 즉시 GC하지 않는다.
- PR #1, #2의 `refs/pull/*`가 옛 커밋을 계속 참조한다. 이 ref는 사용자가 삭제할 수 없다.

완전히 없애려면 GitHub Support에 unreachable 객체 GC를 요청해야 한다. 저장소를 비공개로 전환하면 포크와 함께 즉시 차단되지만, 이번에는 공개 유지를 택했다.

### SHA 변경

히스토리 재작성으로 모든 커밋 SHA가 바뀌었다. 이 문서의 참조는 새 값으로 갱신했다.

| 이전 | 이후 | 내용 |
| --- | --- | --- |
| `9f62aad` | `ee8c782` | Merge pull request #2 |
| `cd3eea6` | `f610f8e` | fix: align report evidence and source selection |
| `f274107` | `88a0bf6` | fix(docker): Cloud Run 표준 exec uvicorn |
| `8c60c34` | `e639f65` | Persist report context across counsel turns |
| `70b1d2b` | `c033547` | Document report context deployment handoff |
| `ba46c96` | `8be2118` | Record verification results |
| `9347ce2` | `efe9bd1` | Configure root logger |
| `03155ec` | `5db2b52` | Quiet httpx and google_genai request logs |
| `b949a7b` | `d54e21b` | Record log noise reduction verification |

Alembic 리비전(`d7f4a1c2e8b9`, `b41d7e6a2f95`), 컨테이너 이미지 digest, 세션 UUID는 Git SHA가 아니므로 그대로 두었다.

### 주의사항

- 재작성 후 로컬 저장소를 `git reset --hard origin/main`으로 맞추면 **`prompts/report.md`가 삭제된다.** 추적 파일이었다가 추적 대상에서 빠졌기 때문이다. 리셋 전에 `prompts/`를 복사해 두고, 리셋 후 되돌려 놓아야 한다. 실제로 이 과정에서 한 번 삭제됐고 메인 체크아웃 사본으로 복구했다(blob 해시 `94db4c73...` 일치 확인).
- 재작성 이전 히스토리를 가진 로컬 브랜치와 worktree가 남아 있으면 force push된 원격과 충돌한다. 각각 `git fetch` 후 리셋해야 한다.
