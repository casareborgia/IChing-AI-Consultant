# E2E 계약 — 제품 소스에서 읽어낸 실제 HTTP 계약

기준 SHA `bbdf758b5b3d5314ca728feafca067e8e7cfd84c`의 `api/routers/counsel.py`,
`api/routers/credits.py`, `api/deps.py`, `services/credit_operation_service.py`,
`services/credit_service.py`에서 그대로 읽었다. 하네스가 필드 이름이나 상태
문자열을 추정하지 않는다. 값이 바뀌면 이 문서가 아니라 제품이 먼저 바뀐 것이다.

## 1. 공통

| 항목 | 값 | 근거 |
| --- | --- | --- |
| 인증 | `Authorization: Bearer <JWT>` | `api/deps.py:require_user` |
| 지원 알고리즘 | ES256(JWKS), HS256(레거시) | 같은 함수 |
| 요구 클레임 | `sub`, `exp`, `iss` / `aud=authenticated` | `options={"require": [...]}` |
| 발급자 대조 | `{SUPABASE_URL}/auth/v1` | `api/deps.py:expected_issuer` |
| 1회 상담 비용 | 10C | `services/credit_service.py:CONSULTATION_CREDIT_COST` |
| 웰컴 크레딧 | 50C | `services/credit_service.py:WELCOME_CREDITS` |
| Idempotency-Key 정규식 | `^[A-Za-z0-9][A-Za-z0-9_.:\-]{7,254}$` | `credit_operation_service.py` |
| 멱등 키 범위 | `(user_id, endpoint, idempotency_key)` UNIQUE | `CreditOperation.__table_args__` |
| lease | 900초 | `OPERATION_LEASE_SECONDS` |
| `Retry-After` | 2초 | `OPERATION_RETRY_AFTER_SECONDS` |
| rate limit | 인증 전 30/분(토큰 해시 또는 IP), 인증 후 사용자 sub 기준 | `api/deps.py` |

`endpoint` 값은 `counsel.start`와 `counsel.turn`이다. 멱등 키의 범위가
endpoint까지 포함하므로 start와 turn에 같은 키를 써도 충돌하지 않는다.

## 2. `POST /api/counsel/start`

요청 본문은 `StartConsultationRequest` 하나다.

```json
{ "question": "1~1000자 문자열" }
```

`session_id`도 `user_id`도 본문에 없다. 사용자는 검증된 JWT의 `sub`에서만 온다.

## 3. `POST /api/counsel/turn`

```json
{ "session_id": "^[a-zA-Z0-9_\\-]+$ (1~64자)", "user_message": "1~1000자" }
```

소유권 검사가 크레딧보다 **먼저** 끝난다. 세션이 없으면 404, 남의 세션이면 403이며
둘 다 크레딧이 움직이기 전이다.

## 4. 성공 응답 본문 (200)

`_build_response_body`가 만든 필드에 종결 메타데이터 네 개가 더해진다.

```
session_id, turn_number, user_facing_message, needs_followup, is_final,
hexagram_id, transformed_hexagram_id, changing_lines, is_crisis,
crisis_resources, is_duplicate, journal_summary, journal_data, focus_rule,
evidences, report_data, report_status, report_error_code,
operation_id, operation_status, credit_delta, remaining_credits
```

`cast_result`, `first_message` 같은 필드는 **존재하지 않는다**.

## 5. 오류 응답 본문

`_error_json`이 만드는 모양 하나로 통일된다.

```json
{ "code": "...", "message": "...", "detail": "...(message와 동일)",
  "operation_id": "선택", "remaining_credits": "선택",
  "retry_after_seconds": "선택" }
```

`detail`은 기존 클라이언트 호환을 위해 `message`와 같은 문구로 함께 들어간다.
`retry_after_seconds`가 있을 때만 `Retry-After` 헤더가 붙는다.

| 상태 | code | 발생 조건 |
| --- | --- | --- |
| 400 | `IDEMPOTENCY_KEY_REQUIRED` | 헤더 없음 |
| 400 | `IDEMPOTENCY_KEY_INVALID` | 정규식 불일치 |
| 401 | (detail만) | 토큰 없음·서명 불일치·만료·aud/iss 불일치 |
| 402 | `INSUFFICIENT_CREDITS` | 잔액 < 10, `remaining_credits` 포함 |
| 403 | (detail만) | 남의 상담 세션에 `/turn` |
| 404 | (detail만) | 없는 세션, 또는 **남의 operation 조회** |
| 409 | `IDEMPOTENCY_KEY_REUSED` | 같은 키 + 다른 `request_hash` |
| 429 | (detail만) | rate limit, `Retry-After: 60` |
| 500 | `PIPELINE_FAILED` / `INTERNAL_ERROR` | 답변 미제공. 최종 0C |
| 503 | `OPERATION_RECOVERED` | lease 만료 복구. 최종 0C |
| 503 | (detail만) | 출시 게이트 미개방 또는 `GENERATION_ENABLED=false` |
| 202 | `OPERATION_IN_PROGRESS` | 같은 키의 작업이 진행 중 |

500 본문에 예외 문자열·스택·DB명·타 사용자 ID는 들어가지 않는다. 문구는
`일시적인 서비스 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.` 고정이다.

## 6. `GET /api/counsel/operations/{operation_id}`

본인 작업만 보인다. 남의 작업은 존재 여부가 드러나지 않도록 **없는 것과 똑같이
404**다. PROCESSING이면서 lease가 만료됐으면 이 조회가 복구를 수행한다.

```json
{ "operation_id": "...", "operation_status": "PROCESSING|SUCCEEDED|RELEASED|REJECTED",
  "credit_delta": 0, "remaining_credits": 0, "result": {}, "error_code": null }
```

저장된 응답 본문이 담기는 키는 **`result`**다. `response_snapshot`이 아니다.
PROCESSING일 때는 `credit_delta`·`remaining_credits`·`result`가 모두 `null`이고
`retry_after_seconds`가 대신 들어온다(이때는 `error_code` 키가 없다).

## 7. `GET /api/me/credits`

```json
{ "remaining_credits": 50, "welcome_granted": true }
```

조회 실패는 503이다. 프런트가 50C를 추정하는 경로를 없애려고 연 엔드포인트다.

## 8. operation 상태와 결제 의미

| status | 의미 | 최종 credit_delta |
| --- | --- | --- |
| `PROCESSING` | 예약됨, 실행 중 | 아직 없음 (`null`) |
| `SUCCEEDED` | 답변 제공 완료 | `-10` |
| `RELEASED` | 답변 미제공 또는 위기 응답 | `0` |
| `REJECTED` | 잔액 부족으로 시작 못함 | `0` |

위기(`BLOCK_CRISIS`) 턴은 사용자에게 응답을 **주고** 크레딧은 되돌린다
(`is_chargeable`). 즉 200 + `operation_status: RELEASED` 조합이 정상이다.

## 9. 출시 게이트 — 이 SHA의 중요한 제약

`/start`와 `/turn`은 `require_service_gate`를 지난다. 그 게이트는
`evaluate_release_gate`의 `free_beta_ready`를 보고, 그 값은
`acceptance_evidence_problems`가 비어야 참이 된다. 그런데

- `core/release_trust.py:APPROVED_ACCEPTANCE_PUBLIC_KEYS = ()` (빈 튜플)
- `core/release_evidence.py:RELEASE_ELIGIBLE_SUITE_VERSIONS = frozenset()` (빈 집합)
- `acceptance_evidence_problems`는 `require_release_eligible=True`로 고정 호출

이 세 가지 때문에 **어떤 환경변수로도, 어떤 서명 manifest로도 게이트가 열리지
않는다.** 이것은 결함이 아니라 의도된 설계다. 전체 출시 suite가 아직 존재하지
않으므로 자격 있는 suite 목록을 비워 둔 것이다.

따라서 이 SHA에서 `/api/counsel/start`와 `/api/counsel/turn`은 모든 환경에서
**항상 503**이다. 상담 경로를 HTTP로 검증하려면 테스트 프로세스에서 게이트
의존성을 우회하는 수밖에 없다. 하네스는 이를 숨기지 않는다.

- `S01`은 override **없이** 돌아 제품 기본값이 503임을 먼저 증명한다.
- 그 뒤에만 `app.dependency_overrides[require_service_gate]`를 건다. 이는
  FastAPI가 테스트용으로 제공하는 표준 기능이며 제품 소스를 바꾸지 않는다.
- 인증(`require_user`)과 rate limit(`check_rate_limit`)은 **override하지 않는다.**

이 제약은 `tests/test_jwt_auth.py`에도 이미 영향을 주고 있다. 그 suite의 8개
테스트는 401을 기대하지만 게이트가 먼저 503을 돌려줘 실패한다. CYCLE-06에서
고치지 않았다 — 제품 경로 판단이 필요한 사안이라 CR로 분리했다.
