# Commercialization Contracts

이 문서는 제품 계약의 상태와 소비자를 추적한다. HTTP의 기계적 원본은 향후 FastAPI
OpenAPI/Pydantic, DB의 기계적 원본은 Alembic migration과 PostgreSQL 제약으로 둔다.
Markdown 설명이 구현과 다르면 이를 자동으로 구현 완료로 간주하지 않는다.

## 계약 상태 규칙

- `DRAFT`: 조사·Mock·실패 테스트만 허용한다.
- `OPERATOR_SELECTED`: 개발 기준값은 선택됐으나 구현·법률·환경·출시 검증은 별도다.
- `AGREED_LOCALLY`: 코드와 폐기 환경 계약은 합의됐으나 원격 적용·검증은 남아 있다.
- `AGREED`: 영향받는 FE·BE·QA 담당이 같은 버전과 의미를 확인했다.
- `DEPRECATED`: 대체 계약과 제거 조건이 기록됐다.
- 기술적 `AGREED`는 운영자 D 결정 또는 출시 승인을 의미하지 않는다.

## 계약 목록

| 계약 | 상태 | 제안 담당 | 소비자 | 현재 근거 |
|---|---|---|---|---|
| `test-safety-v1` | AGREED | Codex | 전체 pytest 작업자 | T00-QA 안전 가드, hash `f6519744a42a20ac725ba244f75ea1b67fd1136b5072b2a70479927b0c08d854` |
| `config-v1` | AGREED | Claude Code | API·FE·QA | fail-closed 범위만: `c905ea4` + 기존 FE 소비자; runtime trust 교체 차단·release suite 비활성·malformed 차단. 실제 출시 suite는 BLOCKED |
| `auth-v1` | AGREED_CANDIDATE / DEV_REDIRECT_REVIEWED | Claude Code | Antigravity·Codex | 실제 ES256 JWT 유효 200·누락/변조 401; 3005 callback 등록·기존 설정 보존·무우회 OAuth를 Antigravity가 독립 재현 |
| `legal-v1` | DRAFT/PARTIAL | Claude Code | Antigravity·Codex | D ID와 거래 없음 단정 정정; 실제 정책 게시·법률 검토는 미완료 |
| `ledger-v1` | AGREED | Claude Code | Antigravity·Codex | 기술 범위: D06 개발값, CYCLE-02 통합 구현과 폐기 PostgreSQL 인수검사 통과 |
| `operation-v1` | AGREED / HARNESS_VERIFIED_API | Claude Code | Antigravity·Codex | 기술 범위: BE·FE 소비자·Codex 보완 및 멱등/복구 인수검사 통과. C06 하네스가 실제 HTTP로 202→SUCCEEDED·재생·409·RELEASED 0C·복구·404를 재확인; 브라우저 레벨은 미검증 |
| `credit-rls-v1` | DEV_VERIFIED | Codex | API·Supabase·QA | 개발 DB 적용·A/B 역할·익명 REST·실 JWT authenticated REST 자기 읽기/operations 403; 상대 독립검수 대기 |
| `e2e-harness-v1` | AGREED_CANDIDATE | Claude Code | Antigravity·Codex | `docs/commercialization/E2E_CONTRACT.md`가 제품 소스에서 추출한 HTTP 계약; C06-R1에서 중앙이 독립 재현(14/14 PASS) |
| `privacy-v1` | DRAFT | Claude Code | Antigravity·Codex | 현재 lifecycle API 없음 |
| `safety-v1` | DRAFT | Claude Code | Antigravity·Codex | 기존 safety/pipeline 동작 조사 필요 |
| `payment-v1` | DRAFT | Claude Code | Antigravity·Codex | Mock provider도 아직 없음 |
| `refund-v1` | DRAFT | Claude Code | Antigravity·Codex | 현재 현금 환불 도메인 없음 |
| `beta-policy-v1` | DRAFT/OPERATOR_SELECTED | 운영자 | Claude Code·Antigravity·Codex | CYCLE-00-R2 개발 기준 선택; 구현·증거·출시 승인 미완료 |

## test-safety-v1

파괴적 DB 테스트는 다음 계약을 따른다.

정규화 문자열은
`test-safety-v1|TEST_DATABASE_URL|postgresql|local-or-unix|database-suffix=_test|confirm=I_UNDERSTAND_THIS_DATABASE_IS_DISPOSABLE|table=public.test_environment_marker|purpose=ICHING_DISPOSABLE_TEST_DB_V1|fail-before-delete-or-ddl`이며 SHA-256은 위 계약 목록에 기록했다.

| 항목 | 값 |
|---|---|
| 대상 URL | `TEST_DATABASE_URL`만 사용 |
| 허용 DB | PostgreSQL, 로컬/Unix socket, 이름이 `_test`로 끝남 |
| 명시적 확인 | `ICHING_TEST_DB_CONFIRM=I_UNDERSTAND_THIS_DATABASE_IS_DISPOSABLE` |
| DB marker 테이블 | `public.test_environment_marker` |
| marker 행 | `purpose = ICHING_DISPOSABLE_TEST_DB_V1` |
| 실패 방식 | DELETE/DDL 및 DB 연결 전에 pytest setup error |
| marker 생성 | 자동 생성 금지; 테스트 DB 준비자가 명시적으로 수행 |
| 외부 API | `live_api` marker가 없는 테스트에서 차단 |

marker 준비 SQL은 `tests/conftest.py`의 fixture 문서에 있다. 비밀번호·실제 URL은
이 문서나 notes에 기록하지 않는다.

## 현재 구현에서 확인한 계약 차이

다음은 기준 SHA의 관찰이며 신규 계약 승인이 아니다.

| 영역 | 현재 동작 | 목표 계약에서 해결할 차이 |
|---|---|---|
| 인증 | HS256/ES256 검증, 개발 dev-token | issuer·계정 상태·구토큰·운영 fail-closed 확인 |
| 제한 | 프로세스 메모리, 토큰 문자열 또는 IP key | 검증 user_id 기반 공유 limiter |
| 크레딧 | `profiles.credit_balance`, append-only ledger, 멱등 operation 예약 | lot·allocation은 유료 판매 범위에서 별도 설계 |
| 비과금 | `BLOCK_CRISIS`와 답변 미제공 pipeline 실패를 release | 프로세스 강제 종료 복구는 lease/fencing으로 terminal 1회 보장 |
| 상담 | 예약 commit 후 장시간 pipeline, 성공/release 별도 확정 | 파이프라인 내부 세션 commit은 원장 lock 밖에서 실행 |
| 암호화 | 일부 카드 필드 AES-GCM, 설정 fallback key | 전용 key_id·AAD·회전·운영 키 누락 거부 |
| 개인정보 | 상담·턴·저널 평문 저장 | 승인된 수명주기·삭제·내보내기 계약 |
| 결제/환불 | 구현 없음 | Mock 우선, PG 확정 전 운영 비활성 |

## beta-policy-v1 운영자 선택 기준

2026-09-08 운영자가 선택한 무료 베타 개발 기준은 다음과 같다.

- 서비스 표시는 `무료 베타 준비 중`으로 유지한다.
- 대한민국 만 19세 이상을 대상으로 하되, 체크박스를 법적 본인확인으로 주장하지 않는다.
- 가입 시 50C를 지급하고, 정상 AI 답변이 제공된 한 턴은 10C를 소비한다.
- `BLOCK_CRISIS`와 답변이 제공되지 않은 기술 장애는 0C로 처리한다.
- 위기 감지 차단은 24시간이며 재감지 시 그 시점부터 24시간을 다시 계산한다.
- 상담·저널은 기본 90일 보관하고 직접 삭제·탈퇴 삭제 경로를 제공한다.
- AI 학습·품질 개선 재사용은 기본 OFF다.
- 크레딧의 현금 가치를 표시하지 않는다.
- 유료 판매·실제 PG·가격·유효기간·환불 공식은 미정이며 비활성으로 둔다.

이는 운영자 선택 전체가 법률 검토나 출시 승인을 받았다는 뜻은 아니다. CYCLE-02 통합
후보에서는 `BLOCK_CRISIS`와 답변 미제공 pipeline 실패의 0C, 가입 50C 1회, 정상 답변
10C가 로컬 폐기 PostgreSQL에서 검증됐다. 따라서 `ledger-v1`의 해당 기술 범위만
기술적 `AGREED`로 기록한다. D01·D03·D10~D13, 정책 게시, Supabase 적용과 출시 증거가
남아 있으므로 무료 베타 게이트는 계속 닫아 둔다.

## CYCLE-02 `credit-operation-v1` 구현 계약

T03은 공통 시작 SHA `b65e73a9edbefab991131eb735fb95aecb140074`에서 구현한다.
Claude Code는 서버·model·migration, Antigravity는 프런트 소비자, Codex는 독립 인수검사와
통합을 담당한다. 상세 allowlist와 도구별 프롬프트는
`notes/codex/CYCLE-02-T03-TASK-CARDS.md`가 기준이다.

| 항목 | 고정 의미 |
|---|---|
| 단위 | 가입 50C, 정상 AI 답변 한 턴 10C |
| 비과금 | `BLOCK_CRISIS`, 답변 미제공 기술 장애 |
| 멱등 범위 | 인증 사용자 + endpoint + `Idempotency-Key` |
| 상태 | `PROCESSING / SUCCEEDED / RELEASED / REJECTED` |
| 동시 재시도 | 처리 중 202, 완료 결과 재생, 다른 body 409 |
| 잔액 출처 | 서버 `GET /api/me/credits`와 operation 결과 |
| 트랜잭션 | 예약 커밋·세션 종료 후 장시간 pipeline 실행 |
| 복구 | lease 만료 + fencing token, terminal 전이 하나 |
| DB 불변조건 | balance 비음수, welcome 사용자별 1회, operation event별 최대 1회 |
| 하위 호환 | 기존 start/turn 결과 유지 + operation 메타데이터 추가 |

Claude `2645c2b`와 Antigravity `d0a1902`를 결합하고 Codex가 다음 경계를 보완했다.

- 첫 잔액 조회에서 welcome 지급을 만든 경우 즉시 commit한다.
- 600초 LLM 호출 상한보다 긴 900초 operation lease를 사용한다.
- `RELEASED` 무결과는 빈 상담 성공이 아니라 terminal 오류다.
- start와 turn 모두 동일 key 상태 확인·재시도 및 새 operation 선택을 제공한다.
- 정상 답변이 전달됐다면 선택적 report 생성 실패만으로 크레딧을 release하지 않는다.

같은 통합 후보에서 migration upgrade→downgrade→upgrade, 기존 DB 테스트 9건, 독립
멱등·동시성·복구 테스트 4건, BE/FE 단위·build가 통과했으므로 이 범위를
기술적 `AGREED`로 올린다. 이는 Supabase 적용, RLS, 실 JWT, 운영 복구 훈련 또는 출시
승인을 뜻하지 않는다.

## CYCLE-00-R1 교차검수로 확인한 계약 경계

| 항목 | 확인된 사실 | 계약 판정 |
|---|---|---|
| 무료 베타 게이트 | `free_beta_ready`는 계산되지만 `/start`·`/turn`은 `GENERATION_ENABLED`만 검사 | `config-v1` AGREED 불가 |
| 유료 출시 게이트 | `PAYMENT_PROVIDER != "mock"`이면 구현 여부와 무관하게 통과 가능 | `commercial_launch_ready`를 출시 승인으로 소비 금지 |
| 카드 인증 | 프런트 `exportCardImageApi`는 Supabase 세션 토큰이 없으면 호출하지 않음 | CR-claude-007 프런트 단계 반영 |
| 카드 서버 인증 | `/api/counsel/card/export`는 rate limit만 있고 `require_user` 없음 | 인증 완료 아님, BLOCKED |
| 무료 베타 표시 | 중앙 게이트는 미승인으로 false인데 화면은 “운영 중” 단정 | 배포 상태 연동 전 공개 문구로 승인 불가 |
| 크레딧 미차감 | 현행 서버는 `BLOCK_CRISIS`만 환불; 시스템 장애 일반 보상은 보장하지 않음 | 약관의 장애 미차감 약속과 불일치 |

CR-claude-007은 두 단계 계약으로 관리한다. 1단계인 프런트 토큰 획득과 무토큰 호출
차단은 `93841df`에서 확인했다. 2단계인 서버 `require_user`, 검증된 `sub` 기준 소유권,
401/429 회귀 테스트가 끝날 때까지 `auth-v1`이나 카드 인증을 완료로 올리지 않는다.

운영자 결정 ID의 유일한 의미는 `PROJECT_CONTROL.md`의 D01~D13 표다. 도구별 note나
화면 주석이 다른 번호를 사용하면 중앙 표를 우선하며, 해당 note는 정정 대상이다.

## CYCLE-00-R2 계약 검수

Claude의 `commercial_config_ready` 추가(CR-claude-010)는 하위 호환적인 DRAFT 필드로
수용할 수 있다. 다만 `commercial_launch_ready`나 `free_beta_ready` 어느 것도 중앙
TEST_MATRIX의 테스트 증거와 운영 승인을 대신하지 않는다.

현재 `free_beta_ready`는 실제 사업자 값, 정책 버전, 게시 상태, 테스트 증빙을 확인하지
않고 `OPERATOR_ATTESTED_DECISIONS`의 D 문자열만 검사한다. 더구나 무료 베타 필수 목록에
D05 위기 차단이 없다. 이 상태에서 상담 API를 직접 여는 것은 작업지시서의 “필수값·정책
버전·운영자 승인·테스트 증빙” 게이트와 불일치하므로 `config-v1`은 AGREED가 아니다.

공개 설정의 활성 상태 계약도 미합의다. 서버 기본 미승인 상태는
`service_stage=free_beta`, `generation_enabled=true`, `policy_documents_draft=true`인데,
프런트는 앞의 두 필드만으로 “무료 공개 베타”를 표시한다. 최소한
`policy_documents_draft=false` 또는 명시적 `free_beta_ready=true`를 함께 요구해야 한다.

Supabase 환경은 다음처럼 나눈다.

| 층 | R2 증거 | 계약 상태 |
|---|---|---|
| 원격 Auth 공개 메타데이터 | 마스킹된 project ref, OIDC/JWKS 200 보고 | CONNECTED_UNVERIFIED |
| 실제 사용자 JWT | C05 기존 사용자 OAuth 발급 ES256; 토큰 비기록, 후보 서버 유효 200·누락/변조 401 | PASS_CANDIDATE |
| 원격 Supabase DB/RLS | 개발 DB head 적용, A/B role+claim 자기 읽기·익명 REST·최소 GRANT 확인 | DEV_APPLIED / ROLE_PASS |
| 로컬 PostgreSQL | 9개 테이블 RLS 없음으로 보고 | 원격 Supabase 증거가 아니며 A08/A09 불충족 |

## CYCLE-01-R3 계약 검수

Claude `e1197a8`은 무료 베타 필수 결정에 D05를 추가하고 다음 DRAFT 증거 필드를
도입했다.

- `LEGAL_DOCUMENTS_VERSION`, `LEGAL_DOCUMENTS_PUBLISHED`
- `FREE_BETA_LAUNCH_APPROVED_BY`, `FREE_BETA_LAUNCH_APPROVED_AT`
- `ACCEPTANCE_EVIDENCE_SHA`, `ACCEPTANCE_EVIDENCE_SUITE_VERSION`

기본값은 모두 닫혀 있고 D ID만으로 게이트가 열리지 않는 점은 계약 개선이다. 그러나
현재 검사는 문자열 형식만 확인한다. 실제 저장소에 존재하지 않는 합성 SHA도 통과하므로
`ACCEPTANCE_EVIDENCE_SHA`는 아직 테스트 통과 증거가 아니라 운영자 입력란이다. CI가
서명하거나 빌드에 고정한 manifest와 대조하기 전에는 `config-v1`을 AGREED로 올리지 않는다.

무료 베타가 50C 지급과 10C 소비를 사용한다면 D06은 유료 판매 전용 결정이 아니다.
T03 계약에서 D06을 무료 베타 필수로 옮기되, 실제 장애 0C·웰컴 중복 지급·원장 차감이
구현되고 독립 검수되기 전에는 공개 게이트를 열지 않는다.

서버 공개 설정에는 하위 호환 필드 `free_beta_ready`가 추가됐다. Antigravity의 소비자는
정상 boolean 입력에서 `service_stage=free_beta`, `generation_enabled=true`,
`policy_documents_draft=false`, `free_beta_ready=true`를 모두 요구한다. 다만 현재 파서는
`Boolean("false") === true`인 JavaScript 변환을 사용하므로 `generation_enabled="false"`를
활성으로 오인한다. 공개 설정은 다음처럼 엄격하게 소비해야 한다.

| 필드 | 허용 타입/값 | 잘못된 타입 처리 |
|---|---|---|
| `service_stage` | allowlist 문자열 | 전체 fallback 또는 비활성 |
| `purchase_enabled` | boolean | false |
| `generation_enabled` | boolean | false |
| `policy_documents_draft` | boolean | true |
| `free_beta_ready` | boolean | false |
| 크레딧 수치 | 유한한 비음수 정수와 정책 상한 | 안전 기본값 또는 설정 오류 표시 |

브라우저 보고에는 base URL·실행 명령·뷰포트·HTTP/console 표가 추가됐지만 파일명을
실제 저장 위치 없이 적었다. 재현 가능한 브라우저 증거 계약은 절대경로 또는 저장소
상대경로, 생성 명령, 비밀 제거 여부와 실제 접근 가능성을 요구한다. 보고서 커밋은 자기
SHA를 본문에 넣지 않고 `this commit`으로 표시하며, 실제 HEAD는 인계 메시지와 중앙 색인에
기록한다. 자기 SHA를 본문에 넣고 다시 커밋하면 SHA가 바뀌는 순환을 만들기 때문이다.

## CYCLE-01-R4 계약 검수

Antigravity `3c2c62a`는 `publicConfig`를 `unknown`에서 시작해 stage allowlist, 정확한
boolean, 유한한 비음수 정수를 검사한다. 잘못된 필드 하나라도 있으면 fallback하고
활성 판정은 기존 네 조건을 모두 요구한다. 이 소비자 타입 계약은 isolated branch에서
코드·25개 단위 테스트로 확인했다. 다만 서버와 같은 통합 후보에서 실행하지 않았으므로
`config-v1` 전체를 AGREED로 올리지는 않는다.

Claude `a2a7ab0`은 D06을 무료 베타 필수 결정으로 옮기고 Ed25519 manifest 검증을
도입했다. 서명·digest·SHA·suite 불일치 거부 자체는 개선이다. 그러나 신뢰 공개키가
`ACCEPTANCE_EVIDENCE_PUBLIC_KEY` 런타임 설정이어서 manifest와 함께 임의 키로 교체할 수
있다. 검수자가 새 키로 자체 서명한 manifest와 맞춘 설정만으로 `free_beta_ready=true`를
재현했으므로 “애플리케이션 설정으로는 통과 불가” 계약은 성립하지 않는다.

또한 `A01-A37/v1`이라는 suite 이름이 요구하는 check는 `release_gate`,
`auth_hardening`, `card_export` 세 개뿐이다. 중앙 A01~A37 중 DB 안전 성공 경로, RLS,
원장·복구, 개인정보, 위기 E2E 등 다수가 BLOCKED/NOT_RUN인데도 유효 서명만 있으면
게이트가 열린다. suite 명칭과 실제 검사 집합은 정확히 일치해야 하며, 무료 베타 출시
manifest는 중앙의 필수 인수기준이 모두 통과하기 전 생성할 수 없어야 한다.

신뢰 anchor는 런타임에서 자유롭게 교체할 수 없는 검토된 빌드 입력 또는 그와 동등한
배포 provenance에 고정한다. 실제 CI·키 관리가 없으면 지원 suite를 열지 않고 운영
게이트를 false로 유지한다. manifest의 모든 값은 집합 조회나 문자열 연산 전에 타입을
검사하고, 어떤 malformed JSON도 예외 대신 명시적 차단 사유로 끝나야 한다.

R4 브라우저 증거 계약은 아직 미충족이다. 파일 경로와 SHA-256은 확인됐지만 360px로
보고한 PNG가 실제 1440px 폭이고, 정상 활성 mock PNG는 화면에서 `무료 베타 준비 중`을
표시한다. viewport 라벨이나 보고 표가 아니라 실제 픽셀·표시 내용·재현 가능한 mock
명령과 network/console 결과가 일치해야 PASS다.

## CYCLE-03 fail-closed·Supabase 적용 계약

`config-v1`은 **게이트가 열리지 않아야 하는 현재 범위에 한해** 기술적으로 합의한다.
승인 공개키는 코드 레지스트리에만 있고 현재 비어 있으며, env의
`ACCEPTANCE_EVIDENCE_PUBLIC_KEY`는 판정에 영향을 주지 않는 deprecated no-op이다.
`development-smoke/v1`은 알려진 suite일 뿐 release 자격이 없고, release-eligible registry도
비어 있다. 64KiB 또는 깊이 8을 넘거나 타입이 잘못된 manifest는 예외·내용 반사 없이
닫힌다. 테스트의 임시 key/suite 주입은 각 테스트 범위의 monkeypatch로만 허용하며 모듈
import가 런타임 registry를 바꾸면 안 된다.

이 합의는 실제 CI 서명, 운영자 승인 공개키, 전체 인수 suite 또는
`free_beta_ready=true` 경로를 승인하지 않는다. 이 세 항목이 정의되기 전에는 게이트가
영구 false인 것이 계약에 맞다.

브라우저 증거는 실제 viewport 픽셀, 제품이 사용하는 정확한 endpoint, 실제 API schema,
`/start`와 `/turn`, 동일 key retry/polling, 저장된 console/network 산출물을 함께 가져야
한다. CYCLE-03 PNG는 모두 1440x779이고 helper에 `/turn`이 없어 A47 증거가 아니다.

T03을 Supabase에 적용하기 전 DB 계약은 다음과 같다.

- `credit_operations`는 RLS를 활성화하고 anon/authenticated의 직접 조회·쓰기를 허용하지
  않으며, 검증된 서버 역할만 접근한다.
- 원격 grants/default privileges도 같은 경계를 보장해야 한다.
- 가입 50C와 `WELCOME` 원장은 DB trigger 또는 백엔드 한 곳만 소유한다.
- 기존 `handle_new_user()`가 있다면 새 `event_type=WELCOME`·멱등 불변조건과 호환되도록
  후속 migration에서 수정하며, 기존 행 backfill은 집계 결과를 검토한 뒤 별도 승인한다.
- backup/restore point와 rollback 한계를 기록하고 개발/staging에서 역할별 거부·허용을
  검증하기 전 원격 upgrade를 수행하지 않는다.

Antigravity의 메타데이터 보고는 `PRE_T03 / REPORTED_READONLY`이며 위 계약을 검증한 것이
아니다. A08/A09와 원격 적용 준비는 계속 BLOCKED다.

## CYCLE-04 `credit-rls-v1` 구현 계약

`e8b72c4a91d0`은 세 크레딧 테이블에서 RLS와 SQL grants를 함께 고정한다. `anon`은 접근
불가, `authenticated`는 자기 profile·ledger SELECT만 가능하며 operation과 모든 직접
쓰기는 불가다. 서버 역할도 DELETE/TRUNCATE 없이 런타임에 필요한 최소 CRUD만 받는다.
정책 drift, 잘못된 과거 웰컴 금액, 사용자별 중복 웰컴 후보가 있으면 전체 transaction을
중단한다.

가입 trigger가 이미 있는 Supabase에서만 함수를 교체하고 `WELCOME` event를 1회 기록한다.
`handle_new_user`, 취약한 구형 `deduct_credit`, event trigger helper, 앱 미사용 search RPC는
Data API 역할이 직접 실행하지 못한다. production seed는 이 함수와 크레딧 DDL을 소유하지
않으며 Alembic을 우회해 재생성해서는 안 된다.

폐기 PostgreSQL에서 PRE_T03→head, 단독·전체 downgrade/upgrade, 역할 SQL assertions,
가입 1회와 모호성 중단을 통과했으므로 계약은 `AGREED_LOCALLY`다. 원격 적용 후 실제
anon/authenticated JWT와 서버 경로를 검증해야 원격 상태를 AGREED/PASS로 올릴 수 있다.

## 제안 API 표면

CYCLE-05 갱신(2026-09-11): 개발 Supabase의 T03+RLS 적용이 완료됐다. 백업 복원 검증과
동일 migration의 로컬 적용 후 원격에 한 트랜잭션으로 적용했으며 기존 profiles/ledger
필드 digest가 일치한다. 역사적 웰컴 3행의 event_type 정규화는 승인된 migration의
데이터 변경이다. 이전 절의 원격 미적용 설명은 C04 당시 기록으로 한정한다.
SQL role+claim 검증은 Auth 서비스가 서명한 JWT 검증을 대체하지 않는다. 그래서 C05에서
실제 기존 사용자 OAuth ES256 JWT를 별도로 후보 서버에 넣어 유효 200, 누락·변조 401을
확인했고, 동일 프런트 소스와 후보 API가 head 복원 DB의 기존 10C를 표시하는 것까지
검증했다. 후보 API의 DB는 head 복원본이므로 원격 API 배포 E2E로 합치지 않는다. 대신
같은 실제 JWT의 PostgREST 요청은 개발 DB에서 자기 profile 1행과 자기 ledger만 반환했고
operations를 403으로 막아 Auth→원격 RLS 경로를 별도 확인했다. Supabase redirect
allowlist에는 2026-09-11 기존 네 항목을 보존한 채
`http://localhost:3005/auth/callback`을 추가했다. 대시보드 새로고침 후 지속됐고, 앱 세션
로그아웃 뒤 Google OAuth를 다시 수행하자 수동 authorization-code bridge 없이
`http://localhost:3005/` 로그인 상태로 복귀했다. callback 페이지는 즉시 루트로 치환되어
1초 단위 경로 폴링에는 포착되지 않았으므로 이 증거를 callback 화면 체류 증거로 확대하지
않는다. Antigravity가 이후 대시보드의 Site URL 불변·기존 네 URL 보존·3005 URL 1회 존재와
수동 bridge 없는 callback→localhost 복귀를 독립 재현했다. 이로써 개발 Auth redirect 설정
차단은 해소됐다. 화면의 잔액은 `잔액 확인 필요`였으므로 해당 실행을 잔액 API PASS로
재분류하지 않으며, 서버 JWT/RLS 독립검수와 출시 판정은 계속 별도다.

CYCLE-06은 이 계약들을 처음으로 실제 HTTP에서 기계 검증했다. Claude 하네스는 제품
소스에서 계약을 읽어 `E2E_CONTRACT.md`로 고정하고, 폐기 PostgreSQL과 결정론적 test-only
파이프라인 위에서 14개 시나리오를 실제 TCP로 통과시켰다. 중앙 검수에서 같은 명령을
독립 재현해 동일한 결과를 얻었다(외부 LLM 0회, 원격 쓰기 0건). 이로써 `operation-v1`의
202·재생·409·RELEASED 0C·복구·타 사용자 404가 단위 테스트가 아닌 HTTP 계약 수준에서
확인됐다.

다만 브라우저 경로는 같은 수준으로 올라오지 못했다. Antigravity의 start/turn/잔액
증거는 2026-09-06에 적재된 코드를 계속 실행 중인 8008 서버를 대상으로 생성됐다. 그
서버에는 `/api/me/credits`도 `/api/counsel/operations/{id}`도 출시 게이트도 없어
무인증 `/start`가 503이 아니라 401을 돌려준다. 따라서 그 증거는 검수 SHA의 계약을
검증하지도, 반증하지도 않는다. `auth-v1`의 OAuth 무우회 복귀만 백엔드 버전과 무관하게
유효하다. 잔액 단일 출처(`/api/me/credits`) 계약은 C05에 이어 C06에서도 브라우저에서
확인되지 않았다 — 제출된 로그인 화면 캡처의 배지가 여전히 `잔액 확인 필요`다.

아래 경로는 모두 DRAFT다. Claude Code의 서버 조사, Antigravity의 소비 상태 확인,
Codex의 실패·호환성 검토 후 기능별로 AGREED 처리한다.

| 영역 | 경로 |
|---|---|
| 공개 법적 문서 | `GET /api/public/legal-documents` |
| 온보딩 | `GET/POST /api/me/onboarding` |
| 동의 | `GET/POST /api/me/legal-events`, `POST /api/me/consents/{purpose}/withdraw` |
| 상담 기록 | `GET /api/me/consultations`, `GET/DELETE /api/me/consultations/{id}` |
| 개인정보 | `POST /api/me/privacy-requests`, `GET /api/me/privacy-requests/{id}` |
| 계정 | `DELETE /api/me/account` |
| 크레딧 | `GET /api/me/credits` |
| 주문 | `POST /api/orders`, `GET /api/me/orders` |
| 결제 | `POST /api/payments/confirm`, `POST /api/payments/webhooks/{provider}` |
| 환불 | `GET /api/me/orders/{id}/refund-quote`, `POST /api/me/orders/{id}/refunds` |
| 지원 | `POST /api/support/tickets` |
| 상담 복구 | `GET /api/counsel/operations/{id}` |

기존 `/api/counsel/start`, `/api/counsel/turn`, `/api/card/export`의 호환성은 별도
명시 없이 깨뜨리지 않는다. 사용자 소유권은 JWT의 검증된 `sub`에서만 결정한다.

## 오류 형태 초안

```json
{
  "code": "OPERATION_IN_PROGRESS",
  "message": "요청을 처리하고 있습니다.",
  "request_id": "opaque-id",
  "retry_after_seconds": 3
}
```

`request_id` 외에 서버 스택, DB명, 토큰, 다른 이용자 ID를 응답하지 않는다. 401,
402, 403, 404, 409, 413/422, 429, 503의 세부 코드는 T01에서 합의한다.

## 데이터 처리 맵 — 기준선 관찰

| 데이터 | 현재 저장 위치 | 현재 보호 | 미확인/필요 조치 |
|---|---|---|---|
| 최초·명확화 질문 | `counsel_sessions` | DB 접근 제어, 앱 필드 암호화 없음 | 보관·RLS·암호화·삭제 |
| 턴 발화·응답 | `counsel_turns` | 앱 필드 암호화 없음 | 동일 |
| 보고서 | `counsel_sessions.report_data` | JSON 저장 | 암호화·내보내기·삭제 |
| 저널 | `journal_entries` | 앱 필드 암호화 없음 | 암호화·삭제 |
| 행동 카드 일부 | 애플리케이션 생성 경로 | AES-GCM 도구 존재 | 실제 저장 중복·키 fallback 조사 |
| 크레딧 | `profiles`, `credit_ledger` | 원자적 balance UPDATE | 유료/무료 분리·보존·멱등성 |
| RAG 고전 자료 | `interpretation_chunks` | 개인 데이터 아님 | 개인 상담과 혼합 금지 |
| 로그·캐시·백업 | 환경별 미확인 | 미확인 | T06에서 공급자별 조사 |

실제 운영 리전, 처리업체, 로그·지원 접근 및 백업은 확인 전까지 계약에 없는 사실로
간주한다. 설정값이나 API 키 존재만으로 운영 승인 또는 원문 전송을 허용하지 않는다.
