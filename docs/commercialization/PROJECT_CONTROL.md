# Commercialization Project Control

상용화 작업의 중앙 작업 보드다. 기술 합의는 `CONTRACTS.md`, 검증 증거는
`TEST_MATRIX.md`, 도구별 상세 보고는 `notes/<tool>/`에서 관리한다. 이 문서의
`APPROVED`와 출시 승인은 운영자만 기록할 수 있다.

## 기준선

| 항목 | 값 |
|---|---|
| 작업 주기 | `CYCLE-05-R1-CROSS-REVIEW` |
| 작업지시서 버전 | v2.2, 2026-09-07 사용자 첨부본 |
| 소스 구현 공통 시작 SHA | `45ebf04f5f2902041b98c14c9a8140a89f1157f3` |
| Codex worktree | `/private/tmp/iching-cycle01-integration` |
| Codex 브랜치 | `codex/cycle-05-dev-apply-e2e` (Private 원격) |
| 통합 후보 | Supabase T03+RLS·실제 JWT PostgREST RLS·후보 API 잔액 조회 PASS; OAuth redirect와 무우회 브라우저 로그인 독립검수 PASS; 전체 E2E·출시 검증은 별도 |
| 상용 출시 준비 | `false` |

운영자 결정(2026-09-08): 현재 서비스는 `무료 베타 준비 중`이며, 연결된 Supabase는
개발용으로 잠정 분류한다. 배포 흔적은 있으나 사실상 운영하지 않는 상태다. 프로젝트
종류와 데이터 존재 여부를 기술적으로 확인하기 전까지 `DEVELOPMENT_ASSUMPTION /
DEPLOYED_INACTIVE_UNVERIFIED`로 기록했다. CYCLE-05-R1 대시보드 증거에서 공급자 측 대상이
`main / PRODUCTION` 브랜치로 표시됨을 확인했다. 운영자는 계속 개발용·비운영으로 사용하지만,
공급자 분류까지 개발 브랜치라고 낮추지 않고 `OPERATOR_DEVELOPMENT_USE /
SUPABASE_MAIN_PRODUCTION_BRANCH`로 병기하며 실제 베타 오픈 근거로 사용하지 않는다.

작업지시서는 아직 이 기준 SHA의 추적 파일이 아니다. 다른 도구에는 동일한 v2.2
첨부본과 기준 SHA를 함께 제공해야 한다.

## 파일 소유권

CYCLE-05 최신 상태(2026-09-11): 운영자의 백업 후 적용 승인과 CLI 로그인 완료에 따라
암호화 논리 백업을 만들고 네트워크 없는 메모리 DB에서 복원·migration을 재현했다.
개발 DB에 `c3a91f4d6b27` + `e8b72c4a91d0`을 한 트랜잭션으로 적용했다. 프로필 3행,
원장 91행의 기존 값은 해시가 일치하며 웰컴 3행만 event_type을 정규화했다.
두 사용자 DB 역할에서 자기 프로필 1행·타인 0행, 세 테이블 익명 REST 401을 확인했다.
실제 Auth 발급 ES256 JWT는 issuer/audience/서명/만료를 통과했고, 누락·변조 토큰은 401이었다.
동일한 프런트 소스와 후보 API를 연결한 Antigravity 브라우저에서 잔액 조회 200과 10C 표시,
console/page/network 오류 0을 확인했다. 후보 API의 DB는 원격 접속 문자열 대신 적용 직전
암호화 백업을 head로 올린 격리 복원본을 사용했으며, 조회 전후 3 profiles/91 ledger/0 operations가
유지됐다. 별도로 실제 JWT의 PostgREST 조회에서 자기 profile 1행, 자기 ledger만 보였고
서버 전용 operations는 403이었다. 후보 API 브라우저 실행은 복원 DB였으므로 원격 후보
배포를 검증한 것은 아니다. 이후 정확한 localhost callback을 allowlist에 추가했고,
Antigravity가 설정 보존과 수동 bridge 없는 OAuth의 localhost 복귀를 독립 검수했다. 해당
브라우저 화면의 잔액은 `잔액 확인 필요`였으므로 이번 재검수는 인증 UI PASS이지 잔액 API
재검증이 아니다. Claude의 코드·문서 검수도 취합했으며, 전체 E2E와 출시 승인은 별도다.
상세: `notes/codex/CYCLE-05-DEV-APPLY-RESULT.md`.

| 영역 | 변경 담당 | 다른 도구 |
|---|---|---|
| `frontend/src/**`, `frontend/public/**`, 프런트 테스트 | Antigravity | 계약·보안·회귀 검수 |
| `frontend/src/lib/api.ts`, `frontend/src/context/AuthContext.tsx` | Antigravity | 서버 계약 변경은 CR 제출 |
| `api/**`, `services/**`, `core/**`, `agents/**` | Claude Code | Codex 독립 검수 |
| `migrations/**`, `alembic.ini`, `docs/DB_SCHEMA_AND_RLS.md` | Claude Code | Codex 적용·head 검사 |
| `tests/conftest.py`, `pytest.ini`, 크레딧 테스트 안전 가드 | Codex | 가드 완화 금지, 변경은 CR 제출 |
| 독립 보안·계약·동시성 테스트, CI·출시 검사 | Codex | Claude Code 테스트 논리 검수 |
| `docker-compose.yml`, 공통 테스트 실행 설정 | Codex | Claude Code DB 의미 검수 |
| `docs/commercialization/PROJECT_CONTROL.md` | Codex 취합 | 운영자만 결정 승인 |
| `docs/commercialization/CONTRACTS.md` | Codex 취합 | 영향 소유자 확인 필요 |
| `docs/commercialization/TEST_MATRIX.md` | Codex 취합 | 각 검수자가 증거 제출 |
| `docs/commercialization/notes/<tool>/**` | 해당 도구 | 다른 도구는 읽기 전용 |

동일 논리 파일의 작성자는 한 명이다. 소유권 변경은 기존 작성 중단, 변경 요청,
새 기준 SHA를 기록한 뒤에만 적용한다.

## 작업 보드

| 작업 주기 | 카드 | 담당 | 상태 | 기준 SHA | 결과/재개 조건 |
|---|---|---|---|---|---|
| CYCLE-00 | T00-QA | Codex | IMPLEMENTED | `cea8858` | 전용 marker DB의 성공 경로 및 독립 검수 필요 |
| CYCLE-00 | T01-BE-SPEC | Claude Code | REVIEWED | `cea8858` | 조사 문서 `676ccdc`, 무료 베타 개정 `9b9b544` |
| CYCLE-00 | T04-FE-DRAFT | Antigravity | NEEDS_FIX | `cea8858` | `93841df`; UI 정정은 확인, 운영 사실·미차감 문구와 D ID 재정정 필요 |
| CYCLE-01 | T01-BE | Claude Code | NEEDS_FIX | `8472065` | `a48b014`; R1 결함은 수정, 실제 운영값·증거 없는 D 문자열 게이트 보완 필요 |
| CYCLE-01 | T02-BE-1 | Claude Code | PARTIAL | `8472065` | `a48b014`; 카드 서버 인증 단위 통과, 실 JWT/RLS·결합 검증 미완료 |
| CYCLE-01 | T01-FE | Antigravity | NEEDS_FIX | `93841df` | 실제 코드 `5eca607b`; 공개 설정 활성 판정과 잔여 무결제 단정 수정 필요 |
| CYCLE-01 | T01-QA-R2 | Codex | REVIEWED | `8534d58` | R2 교차검수 완료, VERIFIED 아님 |
| CYCLE-01-R3 | T01-BE-R3 | Claude Code | NEEDS_FIX | `6cc423a` | 코드 `e1197a8`, 보고 `e71e683`; 형식 증거는 추가했으나 진위 미검증·D06 누락 |
| CYCLE-01-R3 | T01-FE-R3 | Antigravity | NEEDS_FIX | `28cd380` | 코드 `d0971d1`, 실제 보고 `b5fdfe1`; 잘못된 boolean 타입이 활성 상태로 승격됨 |
| CYCLE-01-R3 | T03-QA-SPEC | Codex | IMPLEMENTED | `fce0b41` | 원장·복구 독립 인수기준과 실행 제한 작성; BE 계약 대기 |
| CYCLE-01-R4 | T01-BE-R4 | Claude Code | NEEDS_FIX | `e71e683` | 코드 `a2a7ab0`, 보고 `a8385ce`; D06·서명 검증은 반영, mutable trust root·불완전 suite·예외 미해결 |
| CYCLE-01-R4 | T01-FE-R4 | Antigravity | PARTIAL | `b5fdfe1` | 코드 `3c2c62a`, 보고 `9b07470`; 엄격 타입 통과, 브라우저 viewport·활성 화면 증거 불일치 |
| CYCLE-01-R4 | T01-QA-R4 | Codex | REVIEWED | `d264d10` | R4 독립검수 완료; 코드·테스트·증거·통합 판정 분리, VERIFIED 아님 |
| CYCLE-01-INT | T01-INTEGRATE | Codex | INTEGRATED_FOR_DEVELOPMENT | `a5fc163` | Claude·Antigravity 제품 계열 결합, 비DB 회귀·FE build 통과; 출시 검증 아님 |
| CYCLE-02 | T03-BE | Claude Code | INTEGRATED_FOR_DEVELOPMENT | `b65e73a` | 소스 `2645c2b`, 통합 `7c391db`; Codex 보완 포함 |
| CYCLE-02 | T03-FE | Antigravity | INTEGRATED_FOR_DEVELOPMENT | `b65e73a` | 소스 `d0a1902`, 통합 `5e7ddcf`; Codex 보완 포함 |
| CYCLE-02 | T03-QA-INT | Codex | INTEGRATED_FOR_DEVELOPMENT | `bf458d5` | 폐기 PostgreSQL 인수검사·migration 왕복·결합 회귀 통과; 출시 검증 아님 |
| CYCLE-03 | T04-BE-GATE | Claude Code | INTEGRATED_FOR_DEVELOPMENT | `83dbab4` | 소스 `c905ea4`, 통합 `6220035`; 게이트 보완 통과, 테스트 전역 주입은 Codex가 격리 |
| CYCLE-03 | T04-FE-ENV-E2E | Antigravity | INTEGRATED_EVIDENCE_FAILED | `83dbab4` | 소스 `bbc7bfd`, 통합 `7ec5d7a`; Supabase PRE_T03 보고 유효, viewport·E2E 증거 실패 |
| CYCLE-03 | T04-QA-INT | Codex | INTEGRATED_FOR_DEVELOPMENT | `e87186c` | 독립 회귀 통과; RLS·가입 trigger 선행 전 원격 적용 BLOCKED |
| CYCLE-04 | T03-DB-RLS | Codex | TEMP_SUPABASE_VERIFIED | `4f3badc` | 로컬+전용 임시 Supabase 역할 검증 완료; 기존 개발 DB 적용·실 JWT 결합 대기 |
| CYCLE-05 | T03-DEV-APPLY-E2E | Codex | DEV_AUTH_REDIRECT_REVIEWED | `45ebf04` | 개발 DB 적용·실 JWT RLS·후보 FE/API 잔액 PASS; OAuth redirect 독립검수 통과, 전체 E2E 별도 |
| CYCLE-05-R1 | T05-ANTIGRAVITY-OAUTH-BROWSER | Antigravity | REVIEWED_PASS | `bfb78d6` | `8eafbf7`; 설정 5개 보존·무우회 localhost OAuth PASS, 잔액 API는 재검증 아님 |
| CYCLE-06 | T06-CLAUDE-HARNESS | Claude Code | HARNESS_READY | `f31d29d` | 실제 계약 기반 E2E 하네스; API 14/14 PASS, 외부 LLM 0회, 폐기 DB 격리. E2E_PASS 아님 |
| CYCLE-06 | T06-ANTIGRAVITY-BROWSER | Antigravity | EVIDENCE_INVALID_TARGET | `6e4ebdb` | 인증·viewport 보고는 정직하나 start/turn/잔액 증거가 2026-09-06 구버전 서버 대상 |
| CYCLE-06-R1 | T06-CLAUDE-CENTRAL | Claude Code | INTEGRATED_EVIDENCE_NEEDS_FIX | `a5caa1d` | 제품 변경 0·계통 선형 확인, 하네스 독립 재현 PASS; 브라우저 start/turn/잔액 재실행 필요 |
| CYCLE-06-R2 | T06-CLAUDE-CENTRAL 후속 | Claude Code | ENV_REMEDIATED | `70e43fa` | 운영자 요청으로 8008 검수 SHA 재기동 확인·로컬 개발 DB head 적용(백업 후, 데이터 보존); 잔액 계약 동작 확인, Supabase 미접속 |
| CYCLE-06-R3 | DEC-C06-01 A47 범위 결정 | 운영자/Claude Code | SCOPED | `a7c4cf1` | 게이트 폐쇄 중 브라우저 start/turn을 A47에서 분리해 BLK-C06-05로 출시 전 이월; 잔액 증거 종료. A47은 viewport 사유로 FAIL 유지 |
| CYCLE-07-R1 | T07-CLAUDE-CENTRAL | Claude Code | INTEGRATED / A47_PASS_SCOPED | `0ec0b0c` | 마스킹·viewport 재작업 수용, A47 범위 한정 승격 |
| CYCLE-08 | T08B-CLAUDE-SCOPE | Claude Code | CLASSIFIED | `c69b4a7` | 백엔드 A 20개 분류(미구현 11·미검증 5·판정만 2·결정대기 2), 이월 13건 재평가 제안, 문서·코드 불일치 6건 |
| CYCLE-08 | 묶음 0 B10 해소 | Claude Code | REMEDIATED | `f8beb42` | DB 가드를 fixture opt-in→기본 차단. 개발 DB를 쓰던 테스트 20개 확인 |
| CYCLE-08 | 묶음 1 A 항목 검증 | Claude Code | EVIDENCE_ADDED | `9237c55` | 하네스 시나리오 6개 + A36 단위 테스트 1개 |
| CYCLE-08-R1 | T08-CLAUDE-CENTRAL | Claude Code | INTEGRATED / A10·A36·B01·B10 PASS | 이 커밋 | 반증 방식 재검증, 기계 기록 결함 1건 발견·수정. A02·A35·A37은 부분 증거로 NOT_RUN 유지 |
| CYCLE-07 | T07-ANTIGRAVITY-EVIDENCE | Antigravity | NEEDS_FIX | `6aadbeb` | BLK-C06-02 정정과 viewport 규격은 성공; 계정명 마스킹 2파일 누락·본문 노출·애니메이션 도중 촬영으로 중앙 반려 |
| CYCLE-07-R1 | T07-ANTIGRAVITY-REWORK | Antigravity | ACCEPTED | `b4e54b4` | 마스킹 4/4·본문 2/2 해소, CDP 정착 대기 재촬영으로 viewport 3/3 규격+렌더 PASS |
| CYCLE-07-R1 | T07-CLAUDE-CENTRAL | Claude Code | INTEGRATED / A47_PASS_SCOPED | 이 커밋 | 이미지 육안+픽셀 교차검증 후 수용, fast-forward 통합. A47 승격(범위 한정), A48·VERIFIED 불변 |
| CYCLE-05-R1 | T05-CLAUDE-REDIRECT-REVIEW | Claude Code | REVIEWED_ACCEPTED_ANCESTRY_FAIL | `bfb78d6` | `4e4a147`; 코드·민감정보·FE 계약 PASS, 중앙 상태 모순 발견; 보고 커밋은 main 기반 |

READY는 배정 준비 상태일 뿐 실제 착수나 결과를 뜻하지 않는다. 다른 도구의 notes와
결과 SHA가 전달되기 전에는 IN_PROGRESS 또는 IMPLEMENTED로 추정하지 않는다.

## CYCLE-00-R1 교차검수 판정

`VERIFIED`는 사용하지 않았다. 아래 세 조건은 서로 대체되지 않는다.

| 대상 | 코드 검수 | 필요한 테스트 | 상대 도구 독립 검수 | 통합 판정 |
|---|---|---|---|---|
| Codex T00 `1212bb0` + 보고 `572c509` | 통과 | 거부 경로 통과, marker DB 성공 경로 BLOCKED | Claude가 읽기 전용 검수함 | 조건부 통합 후보 |
| Claude `fa9b038` + `644ab4f` + 정정 `8472065` | **실패: P1 2건** | DB 비의존 41건 통과; 전체 pytest 증거 철회 | Codex 검수 완료 | 수정 필요 |
| Antigravity `7b2e6fe` + 정정 계열 `97344c8..93841df` | **실패: P2 문구 2건** | lint/typecheck 통과; webpack 빌드 통과; Turbopack 독립 재현 BLOCKED | Codex 검수 완료 | 수정 필요 |

코드·테스트·상대 검수 세 칸이 모두 충족돼도 운영자 결정과 출시 승인을 뜻하지 않는다.

## CYCLE-00-R2 교차검수 판정

| 대상 | R1 지적 수정 | 독립 테스트 | Supabase/브라우저 | 통합 재현 | 판정 |
|---|---|---|---|---|---|
| Claude `a48b014` + `6cc423a` | 게이트 배선·임의 PG·서버 카드 인증 통과 | 61 passed | 실제 ES256/JWT·RLS 미검증 | NOT_RUN | 새 P1 수정 필요 |
| Antigravity 제출 `5eca607d…` + `28cd380` | D ID·일반 장애 문구 통과, 운영 상태 부분 실패 | lint/typecheck/webpack 통과; Turbopack BLOCKED | `CONNECTED_UNVERIFIED`; 재현 URL·산출물 없음 | NOT_RUN | SHA 정정 및 코드 수정 필요 |

Antigravity 제출 코드 SHA는 존재하지 않는다. 실제 브랜치 코드 커밋은
`5eca607b3303f0208e104e954fbc0f96bacebd47`이며, 보고서에도 잘못된 SHA가 남아 있어
고정 SHA 기반 통합 후보로 채택하지 않는다.

## CYCLE-01-R3 교차검수 판정

| 대상 | 코드 검수 | 독립 테스트 | 증거 인계 | 통합 재현 | 판정 |
|---|---|---|---|---|---|
| Claude `e1197a8` + `e71e683` | D05·증거 필드·공개 ready 필드는 반영; 증거 진위와 D06은 미해결 | DB 차단 URL에서 91 passed | 코드/보고 SHA와 한계 기록 일치 | NOT_RUN | 부분 통과, 수정 필요 |
| Antigravity `d0971d1` + 실제 `b5fdfe1` | 정상 boolean 4조건은 반영; 문자열 false가 true로 변환 | 단위 14, lint, 순차 typecheck, webpack build 통과 | 보고 SHA는 sibling `c05d1c`; 아티팩트 경로 없음 | NOT_RUN | 수정 필요 |

코드 검수, 테스트 통과, 독립 검수는 각각 별도다. 어느 결과도 VERIFIED 또는 무료 베타
공개 승인으로 올리지 않는다. 두 코드 커밋 모두 후속 수정 전에는 통합 후보가 아니다.

## CYCLE-01-R4 교차검수 판정

| 대상 | 코드 검수 | 독립 테스트 | 증거 인계 | 통합 재현 | 판정 |
|---|---|---|---|---|---|
| Claude `a2a7ab0` + `a8385ce` | D06·서명/변조 검사는 반영; 공개키도 env라 trust root 교체 가능, A01-A37 명칭에 check 3개뿐, malformed suite 예외 | DB 차단 URL에서 130 passed; 추가 부정 재현에서 세 문제 확인 | SHA와 미검증 항목 보고 정상 | NOT_RUN | 수정 필요 |
| Antigravity `3c2c62a` + `9b07470` | 엄격 boolean/stage/credit 파서와 fail-safe 통과 | 단위 25, lint, 순차 typecheck, webpack build 통과 | 경로·SHA-256은 정상; 360 파일이 1440 폭이고 active mock 화면이 preparing | NOT_RUN | 코드-only 조건부 후보, 증거 정정 필요 |

Antigravity의 타입 결함은 제품 코드에서 해소됐지만 작업 묶음의 브라우저 증거는 통과하지
않았다. Claude 게이트는 기본 설정에서 닫혀 있으나, 준비값을 넣는 경로의 신뢰·검사 범위가
안전하지 않아 출시 게이트로 채택하지 않는다. 어느 결과도 VERIFIED 또는 공개 승인으로
올리지 않는다.

## CYCLE-02 T03 개발 통합 판정

| 대상 | 코드 검수 | 필요한 테스트 | 독립 검수 | 증거 인계 | 판정 |
|---|---|---|---|---|---|
| Claude `2645c2b` → `7c391db` | operation·원장·migration 계약 구현, Codex가 잔액 commit과 lease를 보완 | 비DB 53, 기존 DB 9, 독립 DB 4 및 migration 왕복 통과 | Codex 완료 | SHA·한계 기록 정상 | 개발 통합 가능 |
| Antigravity `d0a1902` → `5e7ddcf` | key 수명·202 polling·서버 잔액 구현, Codex가 terminal 오류·turn 재시도를 보완 | FE 42, lint/typecheck/webpack build 통과 | Codex 완료 | 3개 PNG 존재; mobile 라벨 360과 실제 500 불일치 | 코드 개발 통합 가능, 증거 P2 유지 |
| 결합 후보 | 소스 순차 결합 후 6개 결함을 통합 브랜치에서 수정 | 비DB 193 및 폐기 DB 13 최종 재검증 통과 | Codex 완료 | 이 주기 note에 재현 절차 기록 | `INTEGRATED_FOR_DEVELOPMENT`, `NOT_RELEASE_VERIFIED` |

코드 검수, 테스트, 독립 검수, 증거 품질은 각각 분리했다. 로컬 폐기 DB에서 T03 기술
계약을 통과했지만 Supabase migration/RLS, 실제 JWT, 출시 증빙은 검증하지 않았으므로
`VERIFIED`나 공개 승인으로 자동 승격하지 않는다.

## CYCLE-03 사전점검 개발 통합 판정

| 대상 | 코드 검수 | 독립 테스트 | 환경·증거 | 판정 |
|---|---|---|---|---|
| Claude `c905ea4` → `6220035` | trust anchor 코드 고정, release suite 비활성, malformed fail-closed 통과; import 전역 주입은 Codex가 scoped fixture로 보완 | release 정·역순 각 252, 결합 Python 348 passed | CI 서명·승인키·전체 suite 없음 | 개발 통합 가능, 출시 게이트는 닫힘 |
| Antigravity `bbc7bfd` → `7ec5d7a` | read-only 보고와 mock helper 수용; public config 경로는 Codex가 수정 | FE unit 42, lint 0 errors/15 warnings, typecheck/build 통과 | PNG 10개 모두 1440x779, `/turn`·원본 network/console 없음 | 코드/helper 통합, 브라우저 증거 FAIL |
| Supabase | 보고상 PostgreSQL 17.6, Alembic `d7f4a1c2e8b9`, T03 미적용 | 역할별 검증 NOT_RUN | 새 `credit_operations` RLS와 가입 trigger 호환 미정 | `REMOTE_APPLY_NOT_READY` |

두 소스 커밋은 공통 시작의 직접 후손이고 allowlist를 지켰다. 개발 통합은 가능하지만
브라우저 PASS, 서버 인증/RLS PASS, 원격 migration 적용 준비, 출시 VERIFIED는 모두 별개다.

## CYCLE-04 Supabase RLS 판정

| 구분 | 코드 검수 | 독립 테스트 | 원격 상태 | 판정 |
|---|---|---|---|---|
| RLS·grants·welcome migration | fail-closed와 최소 권한 확인 | 로컬 왕복+전용 임시 Supabase 역할·익명 REST 통과 | 기존 개발 DB는 PRE_T03 유지 | `TEMP_SUPABASE_VERIFIED` |
| 구형 seed/RPC | 취약 함수 재생성 경로 제거 | 정적 회귀 통과 | 기존 함수는 원격 적용 전까지 남음 | 로컬 수정 완료, 원격 미해소 |
| A08·A09 | 로컬+임시 Supabase 역할 통과 | 익명 REST 401; Auth 발급 JWT는 NOT_RUN | 기존 개발 DB 미적용 | 계속 BLOCKED |

코드 검수와 로컬 테스트는 통과했지만 원격 적용·실 JWT 검증·복원 준비가 없으므로
`VERIFIED`로 올리지 않는다.

## 환경 및 안전 경계

| 대상 | 현재 확인 | 판정 |
|---|---|---|
| Codex 소스 공간 | 기준 SHA에서 분리된 전용 worktree | 확인 |
| 현재 기본 DB | `docker-compose.yml`의 PostgreSQL 16 + pgvector | 확인 |
| 원격 Supabase Auth | 실제 ES256 JWT 후보 인증 PASS; 3000·3005 callback 등록 확인, 3005 무우회 OAuth 독립 재현 | AUTH_PASS / DEV_REDIRECT_REVIEWED |
| Supabase DB/RLS | 운영자 개발용 대상 head `e8b72c4a91d0`; 공급자 표시는 main/PRODUCTION, A/B 역할·익명 REST PASS | DEV_USE / PROVIDER_PRODUCTION_BRANCH / ROLE_PASS |
| Supabase 분류 규칙 | 공급자 대시보드 표시(main/PRODUCTION)와 운영자 용도(개발·비운영)를 한 값으로 합치지 않는다. CYCLE-06에서도 이중 분류를 그대로 유지한다 | DUAL_CLASSIFICATION_MAINTAINED |
| CYCLE-06 브라우저 대상 서버 | C06-R1 시점: 8008 uvicorn(PID 54265)이 2026-09-06 적재 코드. C06-R2에서 PID 41779로 재기동돼 검수 SHA 라우트 9개·무인증 `/start` 503 확인 | MISMATCH_RESOLVED_C06_R2 |
| CYCLE-06 브라우저 DB 쓰기 | 해당 프로세스의 유일한 DB 연결은 `[::1]:5432`(운영자 로컬 `iching-db`). 원격 Supabase DB 쓰기 없음 | LOCAL_ONLY_CONFIRMED |
| 로컬 개발 DB(`iching-db`) | C06-R2 이전 `d7f4a1c2e8b9`로 head보다 2단계 지연(`credit_operations` 부재)이 `잔액 확인 필요`의 원인. 백업 후 `e8b72c4a91d0` 적용, 행 수 전량 보존 | LOCAL_DB_AT_HEAD |
| 출시 게이트 이중 차단 | `/api/public/config`가 `free_beta_ready:false`·`policy_documents_draft:true`를 주어 FE가 상담 버튼을 비활성화하고, BE는 `require_service_gate`로 503. 게이트는 이 SHA에서 어떤 설정으로도 열리지 않음 | FAIL_CLOSED_BY_DESIGN |
| Supabase 개발 프로젝트 | C06-R2에서 접속하지 않음. head `e8b72c4a91d0`는 CYCLE-05 적용분 그대로이며 재적용·설정 변경 없음 | UNTOUCHED_IN_C06 |
| CYCLE-06 하네스 실행 | 폐기 `iching_e2e_test` 컨테이너, marker 확인 후 자동 삭제, 외부 LLM 0회, 예약 포트 미점유 | DISPOSABLE_ISOLATED |
| 파괴적 DB 테스트 대상 | 암호화 백업을 PostgreSQL 17 tmpfs DB에 복원·head 적용; 읽기 검증 후 제거 예정 | CONFIRMED_EPHEMERAL |
| DB marker | `ICHING_DISPOSABLE_TEST_DB_V1` 확인 후에만 실행 | CONFIRMED_EPHEMERAL |
| 외부 API | 기본 pytest에서 소켓 차단 | 코드 확인 |
| 유료 LLM·PG | 이번 주기 사용 금지 | 미사용 |

파괴적 DB 테스트는 다음 네 조건을 모두 만족해야 한다.

1. `TEST_DATABASE_URL`을 별도로 제공한다.
2. PostgreSQL이며 DB 이름이 `_test`로 끝난다.
3. 로컬 호스트 또는 Unix socket이다.
4. 명시적 확인 문구와 DB 내부 marker가 모두 일치한다.

로컬 주소는 SSH 터널일 수 있으므로 주소 검사만으로 실행하지 않는다.

## 변경 요청과 차단사항

| ID | 종류 | 상태 | 내용 | 해제 조건 |
|---|---|---|---|---|
| BLK-C00-01 | 환경 | OPEN | 실제 Supabase Auth/RLS를 재현할 로컬 환경이 없음 | Supabase 로컬 환경 또는 승인된 전용 테스트 프로젝트 결정 |
| BLK-C00-02 | 환경 | RESOLVED_FOR_CYCLE_02 | 임시 로컬 `*_test` DB와 marker에서 T03 테스트 실행 | 환경은 테스트 후 제거; 다음 파괴 테스트는 다시 준비·확인 |
| BLK-C00-03 | 문서 | OPEN | v2.2 작업지시서가 저장소 추적 파일이 아님 | 사용자 승인 후 v2.3 보완본을 공통 기준 커밋에 반영 |
| CR-CODEX-001 | 문서 | PROPOSED | 권장 CYCLE 표에 빠진 T04-BE/T05-BE/T08/T10/T11 배정 보완 | v2.3 작업지시서에서 완전한 주기표 승인 |
| BLK-C00-R1-01 | Claude | RESOLVED_IN_BRANCH | `free_beta_ready=false` 상담 차단 | `a48b014`, 독립 테스트 통과; 통합 미실행 |
| BLK-C00-R1-02 | Claude | RESOLVED_IN_BRANCH | 임의 provider의 commercial true | `a48b014`, 독립 재현 차단 확인 |
| BLK-C00-R1-03 | Claude/Antigravity | OPEN | 카드 인증 양쪽 코드는 존재하나 결합 안 됨 | 동일 후보에서 실제 session token 200와 직접 무인증 401 |
| BLK-C00-R1-04 | Antigravity | OPEN | 초안 화면이 무료 베타 운영·무결제·장애 미차감을 현재 사실로 단정 | 배포 상태 기반 표시 또는 준비 중 문구, 현행 서버 계약과 일치 |
| BLK-C00-R1-05 | Antigravity | RESOLVED_IN_BRANCH | 정정 note의 D ID 오분류 | 실제 `5eca607b` note에서 중앙 정의로 정정 |
| BLK-C00-R2-01 | Claude | OPEN | D 번호 문자열만으로 무료 베타가 열리고 D05도 필수 목록에서 빠짐 | 실제 필수값·정책 버전·테스트 증거 게이트 및 D05 포함 |
| BLK-C00-R2-02 | Claude/Antigravity | OPEN | 미승인 서버 상태를 FE가 활성 베타로 표시 | `free_beta_ready` 공개 또는 `policy_documents_draft=false`까지 요구 |
| BLK-C00-R2-03 | Antigravity | OPEN | 제출 코드 SHA가 없고 최종 report SHA도 본문과 불일치 | 실제 코드·보고 SHA로 새 정정 커밋 제출 |
| BLK-C00-R2-04 | Antigravity | OPEN | 브라우저 PASS 표에 base URL·실행 명령·스크린샷/로그 없음 | 재현 가능한 비밀 제거 증거 묶음 제출 |
| BLK-C00-R2-05 | 환경 | OPEN | 원격 Supabase는 Auth 공개 메타데이터만 확인, DB/RLS·프로젝트 종류 미확인 | 안전한 프로젝트 분류와 승인된 역할별 검증 |
| CR-C00-R2-06 | Claude | RESOLVED_IN_INTEGRATION | 답변 미제공 기술 장애 0C 정책을 서버 원장·복구에 반영 | CYCLE-02 통합 후보에서 실패 release·멱등 재생·복구 테스트 통과 |
| BLK-C01-R3-01 | Claude | RESOLVED_IN_INTEGRATION | 형식-only 이후 남은 mutable 공개키·suite 범위 문제 | `c905ea4`에서 코드 trust registry와 release-eligible 빈 registry로 fail-closed |
| BLK-C01-R3-02 | Antigravity | RESOLVED_IN_BRANCH | 공개 설정의 문자열 `"false"`가 boolean true로 변환되어 활성 베타 표시 | `3c2c62a`, 독립 타입 회귀 통과; 통합 미실행 |
| BLK-C01-R3-03 | Antigravity | PARTIAL | report SHA·파일 경로·해시는 정정됐으나 viewport와 active mock 화면이 보고와 불일치 | 실제 지정 viewport·응답을 재현한 새 아티팩트와 로그 제출 |
| BLK-C01-R3-04 | Codex | RESOLVED_IN_RECORD | 작업 카드 짧은 SHA를 잘못된 40자리 값으로 전달 | 실제 `32f05bb628521a66d17ecfd461eab8d407cfd724`로 중앙 note 정정 |
| CR-C01-R3-05 | Claude | RESOLVED_IN_BRANCH | 무료 베타도 50C/10C를 사용하지만 D06은 commercial-only 목록에 남음 | `a2a7ab0`에서 무료 베타 필수로 이동; T03 구현 검증은 별도 |
| BLK-C01-R4-01 | Claude | RESOLVED_IN_INTEGRATION | 검증 공개키가 런타임 env라 임의 키·자체서명으로 gate true 가능 | 코드 registry로 이동, env no-op, registry 미등록 상태 독립 검증 |
| BLK-C01-R4-02 | Claude | RESOLVED_IN_INTEGRATION | `A01-A37/v1` 이름과 실제 3-check 범위 불일치 | 허위 suite 제거, development smoke는 release 부적격, release registry 비움 |
| BLK-C01-R4-03 | Claude | RESOLVED_IN_INTEGRATION | `suite_version=[]`에서 uncaught TypeError | 필드 타입 선검사·최상위 fail-closed와 회귀 테스트 통과 |
| BLK-C01-R4-04 | Antigravity | OPEN | 360/768/1440 보고와 파일 픽셀 크기가 다르고 active mock PNG도 preparing 표시 | 재현 mock 명령·정확한 응답·지정 viewport·console/network 로그와 새 캡처 제출 |
| BLK-C03-01 | Claude/Codex | RESOLVED_IN_INTEGRATION | 테스트 모듈 import가 전역 출시 trust registry를 변경해 수집 순서에 의존 | scoped monkeypatch와 import 무변경 회귀, 정·역순 각 252 passed |
| BLK-C03-02 | Antigravity | OPEN_EVIDENCE | PNG 10개가 모두 1440x779이고 recovery 캡처·서술 로그가 시나리오 증거와 불일치 | viewport 구성요소는 C07-R1에서 재현 방법(CDP+정착 대기) 확보. recovery·start/turn 기계 증거는 BLK-C06-05와 함께 대기 |
| BLK-C03-03 | Claude/Codex | RESOLVED_LOCALLY | T03의 `credit_operations`에 RLS·client-deny 정책이 없음 | `e8b72c4` 구현·폐기 DB 통과; 원격은 C04 차단으로 추적 |
| BLK-C03-04 | Claude/Codex | RESOLVED_LOCALLY | 원격 auth 가입 trigger 구형 welcome 계약 | 정의·집계 확인 후 `e8b72c4` 호환·backfill 구현; 원격 미적용 |
| BLK-C04-01 | 운영자/Codex | RESOLVED_C05 | 암호화 백업·로컬 복원 후 개발 DB T03+RLS 적용 완료 | 기존 값 보존 해시와 Alembic head 확인 |
| BLK-C04-02 | Codex/Antigravity | RESOLVED_C05 | 실제 ES256 JWT 유효 200·누락/변조 401, authenticated REST 자기 profile/ledger만 200·operations 403, 후보 FE/API 10C | 원격 RLS와 복원 DB 후보 E2E의 실행 환경 차이를 유지 |
| BLK-C06-01 | Antigravity/운영자 | RESOLVED_C06_R2 | 브라우저 start/turn/잔액 증거가 2026-09-06 코드를 적재한 8008 서버 대상이라 검수 SHA를 검증하지 않음 | 2026-09-11 18:29 검수 SHA 코드로 재기동, 라우트 9개·무인증 `/start` 503 확인. 시나리오 B·C 재실행은 게이트 결정 대기 |
| BLK-C06-02 | Antigravity | RESOLVED_C07 | `network_console_summary.json`의 http_trace에 해당 서버가 낼 수 없는 `operation_status`·`credit_delta`가 관측값으로 기록됨 | `6aadbeb`에서 3개 필드 제거·관측 가능 필드 유지·`balance_before_inferred` 분리·빌드 한정 문구 명시, 중앙 확인 |
| BLK-C06-03 | Antigravity | RESOLVED_C06_R3 | `balance_transitions`의 시작 50C를 같은 커밋의 `auth_logged_in.png`(`잔액 확인 필요`)가 반증 | 원인은 로컬 DB 스키마 지연. C06-R2 head 적용 후 화면 30C = DB 30C 대조 완료, C06-R3에서 마스킹 캡처 `balance_30c_after_local_db_head.png` 접수 |
| BLK-C06-04 | Antigravity | RESOLVED_C07_R1 | 커밋된 PNG 4개에 계정 식별자와 상담 원문이 보이는데 보고서는 마스킹·미저장을 주장 | `b4e54b4`에서 파일별 실측 좌표(`x=876..974`)로 4/4 마스킹, 본문 2/2 마스킹, 과장 문구 정정. 중앙이 육안+픽셀 교차검증 |
| BLK-C06-05 | 전 도구/운영자 | DEFERRED_PRELAUNCH | 브라우저 start/turn·202 polling·비과금 release·멱등 복구가 실제 브라우저에서 미검증 (출시 게이트 폐쇄로 구조적 불가) | 게이트가 정상 경로로 열린 뒤 브라우저 재현. 게이트 우회나 인수증거 위조로 닫지 않는다. A48 선행 조건 |
| BLK-C08-01 | Claude Code | OPEN_PRODUCT | 카드 내보내기가 인증은 요구하나 payload 소유권을 검증하지 않아 인증된 사용자가 임의 카드 데이터를 렌더링할 수 있음 | `api/routers/card.py:77-79`가 T07 선행으로 남긴 대조 경로 구현 후 소유권 검증 추가. 제품 변경이므로 CR 필요 |
| BLK-C04-03 | 운영자 | OPEN | leaked-password protection 비활성 | Auth 운영 설정 검토·활성화 결정 |
| BLK-C05-01 | 운영자/Codex/Antigravity | RESOLVED_C05_INDEPENDENT | Supabase OAuth 개발 callback 누락 | 기존 항목 보존·3005 정확히 1회·Site URL 불변, 수동 bridge 없는 callback→localhost 복귀 독립검수 |
| C02-T03-01 | Codex | RESOLVED_IN_INTEGRATION | 잔액 조회가 welcome 생성 후 commit하지 않아 첫 조회에 50C가 유실될 수 있음 | `/api/me/credits` commit 및 회귀 테스트 추가 |
| C02-T03-02 | Codex | RESOLVED_IN_INTEGRATION | operation lease 180초가 LLM 단일 호출 상한 600초보다 짧음 | lease 900초와 상한 회귀 테스트 적용 |
| C02-T03-03 | Codex | RESOLVED_IN_INTEGRATION | RELEASED 무결과를 FE가 빈 성공으로 처리하고 turn 실패에는 동일 key 복구 UI가 없음 | terminal 오류 처리와 start/turn 공통 복구 UI·테스트 적용 |
| C02-T03-04 | Antigravity | OPEN_EVIDENCE_ONLY | `t03_home_mobile_360px.png`가 실제 500px 폭 | 코드 재작업 없이 다음 브라우저 증거 갱신 때 라벨·viewport 일치 |

## 운영자 결정표

`APPROVED_FOR_DEVELOPMENT`는 운영자가 개발 기준을 선택했다는 뜻이며 실제 공개·법률
검토·기술 검증 완료를 뜻하지 않는다. 유료 정책은 계속 미정이다.

| ID | 결정 | 개발용 기본값 | 상태 |
|---|---|---|---|
| D01 | 사업자·연락처·신고정보 | 상호: 리인베스트먼트, 사업자번호: 771-05-03690, 대표: 이승준, 사업장: 서울특별시 (상세 주소는 문의처 참조), 문의: casareborgia@gmail.com (무료 베타 판매 OFF) | APPROVED_2026-09-12 |
| D02 | 대상 국가·연령 | 대한민국·만 19세 이상; 체크박스가 법적 본인확인을 대체한다고 주장 금지 | APPROVED_FOR_DEVELOPMENT |
| D03 | 개인정보 항목·법적 근거 | 최소수집, 목적별 구분 | NEEDS_REVIEW |
| D04 | 상담 보관·학습 이용 | 상담·저널 90일, 직접 삭제·탈퇴 삭제, 품질 재사용 OFF | APPROVED_FOR_DEVELOPMENT |
| D05 | 위기 차단 | 최초 감지부터 24시간, 재감지 시 다시 24시간, 괘·차감 차단 | APPROVED_FOR_DEVELOPMENT |
| D06 | 판매 단위 | 가입 50C, 정상 AI 답변 1턴 10C, 위기·답변 미제공 장애 0C | APPROVED_FOR_DEVELOPMENT |
| D07 | 상품·가격·유효기간 | 현금가치 표시 없음, 유료 판매·유료 만료 OFF | BETA_SCOPE_APPROVED |
| D08 | 소비 순서·환불 | 무료 베타 중 유료 환불 정책 미정 | DEFERRED |
| D09 | PG 경로 | 실결제 OFF, Phase 2 연동 우선순위: 토스페이먼츠 | APPROVED_2026-09-12 (토스 우선) |
| D10 | 처리업체·리전 | Cloud Run·Supabase·Vercel 사용, 국외 이전 고지. Vertex 추론은 미국(`us-central1`/`us-east5`) 유지 | APPROVED_2026-09-12 (정책 유지) |
| D11 | 공개 표현·안전성 | 자기성찰 도구, 진단·치료 아님 | NEEDS_REVIEW |
| D12 | 보안·파기 운영 | 전용 키·최소권한·복구 필요 | NEEDS_REVIEW |
| D13 | 라이선스 | 코드 MIT, 데이터 CC BY-SA 범위 확인 | NEEDS_REVIEW |

## Notes 색인

| 작업 | 경로 | 결과 SHA | 상태 |
|---|---|---|---|
| T00-QA | `notes/codex/T00-QA-baseline.md` | `1212bb0c9efcb9c4289e257f157d0e07e5155a34` | 작성 완료 |
| CYCLE-00-R1 교차검수 | `notes/codex/CYCLE-00-R1-CROSS-REVIEW.md` | 이번 결과 커밋 | 작성 완료 |
| Claude T01/T02 증거 정정 | `notes/claude/CYCLE-00-R1-T01-T02-BE-EVIDENCE.md` | `8472065d383e8b7a18b0e88d948ac7fc9f9b011e` | 반영 완료 |
| Antigravity T04 정정 | `notes/antigravity/CYCLE-00-R1-T04-FE-DRAFT-CORRECTION.md` | `93841df886983042836c73eb04e8d6f026a213d1` | 반영 완료, 추가 정정 필요 |
| Claude R2 수정 | `notes/claude/CYCLE-00-R2-T01-T02-BE-FIX.md` | `6cc423a8e7e80a17e192a7399b69c8fadc850e8d` | 검수 완료, 새 P1 발견 |
| Antigravity R2 수정 | `notes/antigravity/CYCLE-00-R2-ENV-FE-FIX.md` | `28cd380d0ab94ddb2486eb720cb9aed802d358f6` | SHA·증거 정정 필요 |
| CYCLE-00-R2 교차검수 | `notes/codex/CYCLE-00-R2-CROSS-REVIEW.md` | 이번 결과 커밋 | 작성 완료 |
| CYCLE-00-R2 운영자 결정 | `notes/codex/CYCLE-00-R2-OPERATOR-DECISIONS.md` | 이번 결과 커밋 | 개발 정책 기록 완료 |
| CYCLE-01-R3 작업 카드 | `notes/codex/CYCLE-01-R3-TASK-CARDS.md` | 이번 결과 커밋 | 병렬 카드·T03 QA 기준 작성 완료 |
| Claude CYCLE-01-R3 | `notes/claude/CYCLE-01-R3-T01-BE-R3.md` | `e71e6831862501eb43baae178e727e99045f9b7c` | 검수 완료, 수정 필요 |
| Antigravity CYCLE-01-R3 | `notes/antigravity/CYCLE-01-R3-T01-FE-R3.md` | 실제 `b5fdfe19374310115c71fecdbd02ce4a34ca95ce` | 검수 완료, SHA·증거 수정 필요 |
| CYCLE-01-R3 교차검수 | `notes/codex/CYCLE-01-R3-CROSS-REVIEW.md` | 이번 결과 커밋 | 작성 완료, VERIFIED 아님 |
| CYCLE-01-R4 작업 카드 | `notes/codex/CYCLE-01-R4-TASK-CARDS.md` | `b9d0a5acebf20a7a5b32d5a5f13e28eeb3fa00fe` | Claude·Antigravity 수정 지시와 Codex 후속 검수 기준 |
| Claude CYCLE-01-R4 | `notes/claude/CYCLE-01-R4-T01-BE-R4.md` | `a8385ce7885c082fc7a206306ec6eee900255807` | 검수 완료, trust root·suite·예외 수정 필요 |
| Antigravity CYCLE-01-R4 | `notes/antigravity/CYCLE-01-R4-T01-FE-R4.md` | `9b07470519264a356d1365dcbb335afa9ef0283b` | 코드 통과, 브라우저 증거 정정 필요 |
| CYCLE-01-R4 교차검수 | `notes/codex/CYCLE-01-R4-CROSS-REVIEW.md` | 이번 결과 커밋 | 작성 완료, VERIFIED 아님 |
| CYCLE-01 개발 통합 | `notes/codex/CYCLE-01-DEVELOPMENT-INTEGRATION.md` | this commit | 별도 브랜치 통합·결합 검증 완료, 출시 차단 유지 |
| CYCLE-02 T03 작업 카드 | `notes/codex/CYCLE-02-T03-TASK-CARDS.md` | this commit | 비중복 구현 2개와 단회 Codex 통합 지시 |
| Claude CYCLE-02 T03 | `notes/claude/CYCLE-02-T03-BE.md` | `2645c2b923929e0204703d6ecdfb245cb4bd90af` | 개발 통합·독립 검수 완료 |
| Antigravity CYCLE-02 T03 | `notes/antigravity/CYCLE-02-T03-FE.md` | `d0a190210ae1330d14a35a2c60e726900ee54bf2` | 코드 통합 완료, mobile 증거 라벨 불일치 |
| CYCLE-02 T03 개발 통합 | `notes/codex/CYCLE-02-T03-INTEGRATION.md` | this commit | 결합·보완·폐기 DB 인수검증 완료, 출시 차단 유지 |
| CYCLE-03 사전점검 작업 카드 | `notes/codex/CYCLE-03-PREFLIGHT-TASK-CARDS.md` | this commit | Claude·Antigravity 병렬 1회와 Codex 단회 통합 지시 |
| Claude CYCLE-03 T04 | `notes/claude/CYCLE-03-T04-BE-GATE.md` | `c905ea4e67bf4d579e3bdfa74739d8a56aaf8159` | 개발 통합, CI·release suite BLOCKED |
| Antigravity CYCLE-03 T04 | `notes/antigravity/CYCLE-03-T04-FE-ENV-E2E.md` | `bbc7bfd271d768ecbb0b3573654184722d6138f3` | PRE_T03 보고 수용, 브라우저 증거 FAIL |
| CYCLE-03 사전점검 개발 통합 | `notes/codex/CYCLE-03-PREFLIGHT-INTEGRATION.md` | this commit | 개발 통합, 원격 적용 준비 BLOCKED |
| CYCLE-04 Supabase RLS 통합 | `notes/codex/CYCLE-04-SUPABASE-RLS-INTEGRATION.md` | this commit | 로컬 검증 완료, 명시적 개발 DB 적용 승인 대기 |
| CYCLE-05 개발 DB 적용·Auth E2E | `notes/codex/CYCLE-05-DEV-APPLY-RESULT.md` | this commit | 개발 DB·실 JWT/RLS·후보 잔액 PASS, redirect 설정·독립검수 대기 |

## 통합 이력

CYCLE-01 제품 코드를 `codex/cycle-01-integration`에 통합했다. 소스→통합 SHA와 명령별
증거는 `notes/codex/CYCLE-01-DEVELOPMENT-INTEGRATION.md`에 기록했다. 이는
`INTEGRATED_FOR_DEVELOPMENT`이며 `NOT_RELEASE_VERIFIED`다. Claude R4 차단과
Antigravity 브라우저 증거 오류는 출시 차단으로 유지한다. main, push, PR, 실제 배포는
수행하지 않았다.

CYCLE-02 T03은 같은 worktree의 `codex/cycle-02-t03-integration`에서 Claude
`2645c2b`를 `7c391db`로, Antigravity `d0a1902`를 `5e7ddcf`로 순차 통합했다.
Codex 보완과 폐기 DB 인수검증의 상세 내용은 CYCLE-02 통합 note에 둔다. `main`, push,
PR, Supabase 변경, 실제 배포는 수행하지 않았다.

CYCLE-03은 같은 worktree의 `codex/cycle-03-preflight-integration`에서 Claude
`c905ea4`를 `6220035`로, Antigravity `bbc7bfd`를 `7ec5d7a`로 순차 통합했다. Codex는
테스트 trust registry 격리와 mock public-config 경로만 보완했다. Supabase에는 어떤
변경도 하지 않았으며 RLS와 가입 trigger 선행 조건 때문에 원격 적용은 승인 대상이 아니다.

CYCLE-04는 `codex/cycle-04-supabase-rls`에서 그 선행 조건을 migration으로 구현하고
Supabase-like 폐기 DB에서 역할·왕복·기존 행·모호성 중단을 검증했다. 원격에는 읽기 전용
메타데이터·집계 조회만 했고 migration, 정책, 데이터 변경은 하지 않았다.

CYCLE-05는 운영자 승인 후 암호화 백업·복원 검증을 거쳐 개발 Supabase를 head로 올렸다.
실제 ES256 JWT의 후보 서버 검증과 authenticated REST RLS, 동일 FE 소스·후보 API·head
복원 DB 잔액 화면을 각각 통과했다. 제품 소스·main·배포는 바꾸지 않았고, localhost OAuth
redirect allowlist는 2026-09-11 기존 항목 보존 확인 후 정확한 3005 callback을 추가했고 수동
bridge 없는 재로그인이 localhost 루트로 복귀했다. 상대 독립검수는 계속 차단 상태다.

CYCLE-06은 `claude/cycle-06-central-integration`에서 취합했다. Claude가 제품 소스에서
읽어낸 계약으로 로컬 E2E 하네스를 만들어 API 14개 시나리오를 통과시켰고(외부 LLM 0회,
폐기 DB 격리, 원격 쓰기 없음), 중앙 검수에서 내가 같은 명령을 독립 재현해 같은 결과를
얻었다. Antigravity의 브라우저 증거는 OAuth 인증과 viewport 실패 보고가 정직했지만,
start/turn/잔액 증거가 2026-09-06 코드를 적재한 채 계속 돌고 있던 8008 서버를 대상으로
생성돼 검수 SHA의 계약을 검증하지 못했다. 그 서버에는 `/api/me/credits`도
`/api/counsel/operations/{id}`도 출시 게이트도 없다. 제품 코드는 이번 주기에 한 줄도
바뀌지 않았고 제품 결함은 관측되지 않았다. A47·A48과 출시 `VERIFIED`는 승격하지 않았다.

## 출시 게이트

```json
{
  "code_verified": false,
  "policy_approved": false,
  "provider_test_verified": false,
  "pg_review_status": "NOT_SUBMITTED",
  "production_change_authorized": false,
  "commercial_launch_ready": false,
  "blocking_ids": [
    "D01",
    "D02",
    "D03",
    "D04",
    "D05",
    "D06",
    "D07",
    "D08",
    "D09",
    "D10",
    "D11",
    "D12",
    "D13",
    "A01-A48",
    "B01-B10"
  ],
  "next_safe_action": "CYCLE-05-R1 통합 SHA에서 전체 start/turn·복구 E2E 설계를 확정하고 별도 카드로 실행; migration 재적용 불필요"
}
```
