# Commercialization Test Matrix

판정 값은 `PASS / FAIL / NOT_RUN / BLOCKED`만 사용한다. 브랜치 단독 결과와 통합
후보 결과를 분리하고, 검증 대상 코드가 바뀌면 영향받은 PASS를 승계하지 않는다.

## CYCLE-00~CYCLE-05-R1 실행 환경

| 항목 | 값 |
|---|---|
| 최초 기준 / CYCLE-04 시작 SHA | `cea885846147970030aa27fdbce8ad075ec873e5` / `4f3badc9214355cc0143c411f4e82f1e653c6122` |
| 브랜치 | `codex/cycle-05-dev-apply-e2e`; Private 원격, `main` 미변경 |
| worktree | 전용 `/private/tmp/iching-cycle01-integration`; CYCLE-03 통합 commit에서 분기 |
| Python 테스트 실행기 | 기존 프로젝트 `.venv`, Python 3.9.6, pytest 8.4.2 |
| 파괴적 테스트 DB | 임시 pgvector/PostgreSQL 16 `*_test` 2개; marker 확인, 합성 데이터만 사용, 종료 시 제거 |
| Supabase Auth/RLS | C05 대상 head `e8b72c4a91d0`; DB 역할/익명 REST·실제 ES256 JWT PASS, 3005 OAuth redirect 독립검수 PASS; 대시보드 공급자 표시는 `main / PRODUCTION`, 운영자 용도는 개발·비운영 |
| 외부 API·유료 호출 | C05 Supabase 백업·migration·읽기 검증 사용; 유료 LLM/PG 미사용 |

## CYCLE-05 신규 증거 (2026-09-11)

| 증거 ID | 검사 | 결과 |
|---|---|---|
| EV-C05-01 | CLI 로그인·복원 지점 조회 | PASS: 로그인 확인; 서버 백업 목록 0, PITR false |
| EV-C05-02 | 스키마·Auth/Storage 포함 복원 스키마·data·roles 암호화 백업 | PASS: 4파일 복호화, SHA-256 기록; Git 외부 |
| EV-C05-03 | PostgreSQL 17 메모리 DB에 스키마+data 복원 | PASS: 3 profiles, 91 ledger, 3 auth users, 56 sessions, 100 turns, 2536 chunks; profile/auth·ledger/profile orphan 0 |
| EV-C05-04 | 복원 DB에서 고정 migration SQL 적용 | PASS: head `e8b72c4a91d0`, 위 행 수 보존 |
| EV-C05-05 | 개발 DB 트랜잭션 적용+전후 digest | PASS: profiles 전체 값·ledger 기존 필드 동일; WELCOME 3행 정규화, operation 0 |
| EV-C05-06 | anon/authenticated/service_role grants와 네 함수 권한 | PASS: client write/operation 차단, server 최소 grants, 네 함수 Data API EXECUTE false |
| EV-C05-07 | 사용자 A/B 실제 DB 역할+claim 읽기 | PASS: 각각 profile 1, 타 profile·타 ledger 0; READ ONLY/ROLLBACK |
| EV-C05-08 | 익명 REST 세 테이블 | PASS: profiles/credit_ledger/credit_operations HTTP 401; 응답 사용자 행 미수집 |
| EV-C05-09 | 실제 Auth 발급 JWT·후보 서버 인증 | PASS: 기존 사용자 ES256, issuer/audience/sub/만료·서명 유효 200; 누락·변조 401; 토큰 값 미기록 |
| EV-C05-10 | 상대 도구 독립 검수 | PASS: Antigravity 설정·브라우저, Claude 코드·기록 검수 취합; 서버 JWT/RLS 재판정은 범위 밖 |
| EV-C05-11 | 적용 후 기존 배포 API `/health` | PASS: HTTP 200; 신규 API 배포/상담 E2E 증거는 아님 |
| EV-C05-12 | 실제 로그인 FE→후보 API→head 복원 DB 잔액 | PASS: 동일 FE `src`, 후보 PID 로그와 HTTP 200 6건 일치, 화면 10C, 1440x779@1x, console/page/network 오류 0; 기존 wildcard 8008 프로세스 caveat 기록 |
| EV-C05-13 | 브라우저 조회 후 복원 DB 보존 | PASS: profiles/ledger/operations 3/91/0, 음수 잔액 0; 임시 localhost 세션 제거 |
| EV-C05-14 | 수정 전 Supabase OAuth callback 자동 복귀 | FAIL: 요청한 localhost callback이 배포 루트로 치환; code는 수동으로 원래 callback에 전달해야 교환됨 |
| EV-C05-15 | 실제 JWT authenticated REST→개발 RLS | PASS: profiles 자기 1행, ledger 반환 전부 자기 소유, credit_operations HTTP 403; 응답·토큰 미저장 |
| EV-C05-16 | 수정 후 Supabase URL 설정 독립검수 | PASS: Site URL 불변, 기존 4개 보존, `http://localhost:3005/auth/callback` 정확히 1회; 마스킹 PNG 1440x779 |
| EV-C05-17 | 수정 후 Google OAuth 브라우저 독립검수 | PASS: 요청 redirect_to·callback 3005, 수동 bridge 없음, localhost 루트 복귀·로그인 UI·오류 0; 사후 로그아웃 |
| EV-C05-18 | Antigravity 로그인 화면의 크레딧 | NOT_RUN: 화면은 `잔액 확인 필요`; 인증 UI PASS를 잔액 조회 PASS로 확대하지 않음 |
| EV-C05-19 | Claude 문서·코드 독립검수 | PASS: 범위·민감정보·redirect 계약·FE 42 tests·typecheck·lint; Supabase/브라우저는 해당 도구에서 BLOCKED |
| EV-C05-20 | 제출 SHA 계통·allowlist | FAIL: Antigravity `8eafbf7`은 `bfb78d6` 직접 후손·허용 3파일이나 Claude `4e4a147`은 main 기반; 단일 note 내용만 cherry-pick |

과거 표의 원격 미적용/BLOCKED와 EV-C05-14는 당시 기록이다. 이후 Auth redirect 설정과
무우회 브라우저 흐름은 독립검수를 통과했다. 원격 DB 역할 검증과 후보 Auth/FE/API 검증은
각각 통과했지만 한 요청에서 원격 DB까지 결합한 전체 상담 E2E는 없으므로 결과를 자동
VERIFIED로 올리지 않는다.

## 이번 주기 증거

| 증거 ID | 명령/검사 | 결과 | 관련 기준 |
|---|---|---|---|
| EV-C00-01 | `pytest --collect-only tests/test_credit_system.py -q` | PASS, 9건 수집 | A01 |
| EV-C00-02 | TEST_DATABASE_URL·확인 문구 없이 크레딧 테스트 1건 실행 | PASS: DB 연결 전 setup 차단 | A01 |
| EV-C00-03 | 원격 `.invalid` PostgreSQL URL과 opt-in으로 크레딧 테스트 실행 | PASS: DB 연결 전 호스트 차단 | A01 |
| EV-C00-04 | `pytest tests/test_hexagram_engine.py -q` | PASS, 10건 | A02·기존 회귀 |
| EV-C00-05 | 전용 marker DB에서 크레딧 테스트 | BLOCKED: DB 미제공 | A01·A11~A17 |
| EV-C00-06 | Supabase anon/A/B/server 역할 RLS | BLOCKED: 환경 없음 | A08·A09 |
| EV-C00-07 | `_test` 접미사가 없는 로컬 URL과 opt-in으로 크레딧 테스트 실행 | PASS: DB 연결 전 이름 차단 | A01 |
| EV-R1-01 | 세 worktree status/branch/HEAD/merge-base 및 고정 SHA ancestry | PASS | B01·B02 |
| EV-R1-02 | Claude DB 차단 URL로 release/auth/card 테스트 | PASS, 41건; DB 연결 없음 | A04·A05·A06·A10 일부 |
| EV-R1-03 | Claude 기존 전체 pytest 188/205 기록 | FAIL: A/B 증거에서 철회, 개발 DB 전량 DELETE 동반 | A01·B10 |
| EV-R1-04 | `PAYMENT_PROVIDER=not-implemented` 게이트 재현 | FAIL: `commercial_launch_ready=true` | A04 |
| EV-R1-05 | 상담 라우터 dependency introspection | FAIL: `free_beta_ready` 검사 없음 | A04 |
| EV-R1-06 | Antigravity `npm run lint` | PASS, 0 errors/16 warnings | A18~A20 UI 정적 품질 |
| EV-R1-07 | Antigravity `npx --no-install tsc --noEmit` | PASS | A18~A20 UI 정적 품질 |
| EV-R1-08 | Antigravity `npm run build` | BLOCKED: Turbopack가 로컬 port bind EPERM | A18 |
| EV-R1-09 | Antigravity `next build --webpack` | PASS, 13개 정적 페이지 | A18 |
| EV-R1-10 | CR-claude-007 정적 대조 | PASS: export 함수의 session token/무토큰 차단; 서버 인증은 없음 | A06 일부 |
| EV-R2-01 | Claude 시작→코드→보고 SHA ancestry와 allowlist | PASS | B01·B04 |
| EV-R2-02 | Claude 연결 불가 DB URL로 release/auth/card 테스트 | PASS, 61건/14 warnings | A04·A06 일부 |
| EV-R2-03 | R1 게이트·임의 provider·카드 무인증 재현 | PASS: 3건 모두 수정됨 | A04·A06 일부 |
| EV-R2-04 | D 문자열만 입력한 무료 베타 게이트 | FAIL: 실제 값·증거 없이 열림, D05 필수 아님 | A04 |
| EV-R2-05 | Claude 공개 config와 Antigravity 활성 판정 결합 대조 | FAIL: 서버는 미승인인데 FE는 활성 베타 표시 | A05 |
| EV-R2-06 | Antigravity 제출 코드 SHA 확인 | FAIL: `5eca607d…` 없음; 실제는 `5eca607b…` | B01·B06 |
| EV-R2-07 | Antigravity lint/typecheck | PASS, 0 errors/16 warnings; typecheck 0 | A18 UI 품질 |
| EV-R2-08 | Antigravity `npm run build` | BLOCKED: Turbopack local port bind EPERM | A18 |
| EV-R2-09 | Antigravity webpack build | PASS, 13개 정적 페이지 | A18 |
| EV-R2-10 | Antigravity 브라우저 증거 검토 | BLOCKED: 경로·뷰포트 표는 있으나 base URL·명령·스크린샷/로그 없음 | A47·B06 |
| EV-R2-11 | Supabase 환경 note 정적 검수 | PASS: CONNECTED_UNVERIFIED·마스킹·무쓰기 보고; 원격 DB/RLS는 미검증 | A06·A08·A09 |
| EV-R2-12 | 운영자 추천안 선택 기록 | PASS: 개발 정책 입력값 기록; 구현·테스트·법률·출시 증거는 아님 | D02·D04·D05·D06·D07·D09 |
| EV-R3-01 | 양쪽 status·branch·시작→코드→실제 HEAD ancestry와 allowlist | PASS: clean, 코드 변경 허용 범위 내 | B01·B02·B04 |
| EV-R3-02 | Claude DB 차단 URL로 release/auth/card 테스트 | PASS, 91건/14 warnings | A04·A05·A06 일부 |
| EV-R3-03 | D ID만 입력·D05 누락·증거 필드 누락 회귀 | PASS: 모두 `free_beta_ready=false` | A04 일부 |
| EV-R3-04 | 존재하지 않는 합성 `012345…` SHA로 완성 fixture | FAIL: 형식만 맞으면 `free_beta_ready=true` | A04·A48 |
| EV-R3-05 | Antigravity publicConfig 단위 테스트 | PASS, 14건; 정상 boolean·404·500·invalid JSON·timeout | A05 일부 |
| EV-R3-06 | Antigravity lint | PASS, 0 errors/16 warnings | A18 |
| EV-R3-07 | Antigravity webpack build | PASS, 13개 정적 페이지 | A18 |
| EV-R3-08 | Antigravity typecheck | PASS: build 완료 후 단독 재실행 0; 동시 실행은 `.next/types` 경합으로 실패 | A18 |
| EV-R3-09 | `generation_enabled="false"`, 나머지 활성 조건 응답 | FAIL: Boolean 변환으로 `active=true` | A05 |
| EV-R3-10 | Antigravity 브라우저 보고 메타데이터·아티팩트 검사 | BLOCKED: URL·명령·뷰포트 표는 추가, 스크린샷·녹화 파일 경로/파일 없음 | A47·B06 |
| EV-R3-11 | Antigravity 보고 SHA ancestry | FAIL: note의 `c05d1c`는 실제 HEAD `b5fdfe1`의 sibling | B06 |
| EV-R3-12 | Codex 작업 카드 SHA 정정 | PASS: 오기된 40자리 값을 실제 `32f05bb62852…`로 중앙 note 정정 | B06 |
| EV-R4-01 | 양쪽 clean status, 시작→코드→보고 ancestry와 allowlist | PASS | B01·B02·B04 |
| EV-R4-02 | Claude DB 차단 URL로 evidence/release/auth/card 선택 테스트 | PASS, 130건/14 warnings | A04·A06 일부 |
| EV-R4-03 | 형식상 SHA·기존 문자열만 있고 manifest 없음 | PASS: `free_beta_ready=false` | A04 일부 |
| EV-R4-04 | 검수자 임의 Ed25519 키·자체서명 manifest·맞춘 env 설정 | FAIL: `free_beta_ready=true`, blocking 없음 | A04·A48 |
| EV-R4-05 | `A01-A37/v1` manifest의 필수 check 범위 | FAIL: release_gate/auth/card 3개만 PASS해도 gate true | A04·A48 |
| EV-R4-06 | signed manifest의 `suite_version=[]` | FAIL: 차단 목록 대신 uncaught `TypeError` | A04·A10 |
| EV-R4-07 | Antigravity publicConfig 단위 테스트 | PASS, 25건 | A05 |
| EV-R4-08 | Antigravity lint→typecheck→webpack build 순차 실행 | PASS: 0 errors/16 warnings, typecheck 0, 13개 정적 페이지 | A18 |
| EV-R4-09 | 잘못된 boolean/stage/credit 독립 코드·테스트 검수 | PASS: 전체 fallback, 활성 false | A05 |
| EV-R4-10 | 브라우저 아티팩트 경로·SHA-256 | PASS: 8개 파일 모두 존재, 보고 hash 일치 | B06 일부 |
| EV-R4-11 | 브라우저 viewport·표시 내용 | FAIL: 360px 파일 2개가 1440px 폭, active mock 화면도 preparing 표시 | A47·B06 |
| EV-R4-12 | 보고 SHA `this commit`과 실제 HEAD ancestry | PASS: Claude `a8385ce`, Antigravity `9b07470` | B06 일부 |
| EV-INT-01 | 중앙 `a5fc163`에서 제품 코드 계열 순차 cherry-pick | PASS: 충돌 없음, 소스→통합 SHA 기록 | B01·B08 |
| EV-INT-02 | 통합 diff와 줄 끝 공백 정리 후 `git diff --check` | PASS | B04·B09 |
| EV-INT-03 | 통합 브랜치 Python 비DB 선택 테스트 | PASS, 140건/14 warnings | A02·A04·A06 일부·B09 |
| EV-INT-04 | 통합 브랜치 FE 단위→lint→typecheck | PASS: 25건, 0 errors/16 warnings, typecheck 0 | A05·A18·B09 |
| EV-INT-05 | 비접속 placeholder 공개 env로 webpack build | PASS, 13개 정적 페이지 | A18·B09 |
| EV-INT-06 | 기본 서버 release/public config | PASS: free/commercial false, draft true, purchase false | A04·A05 |
| EV-INT-07 | 운영 DB·Supabase·실 JWT·T03 원장 결합 | BLOCKED/NOT_RUN | A08·A09·A11~A17·A48 |
| EV-C02-01 | 소스 worktree status/branch, 시작 SHA ancestry, 카드 allowlist | PASS: 양쪽 clean, `b65e73a`의 직접 후손, 허용 파일만 변경 | B01·B02·B04 |
| EV-C02-02 | Claude 소스의 DB 차단 URL unit | PASS, 52건 | A11~A17 일부 |
| EV-C02-03 | Antigravity 소스 unit/lint/typecheck/webpack build | PASS: unit 40, 0 errors/15 warnings, typecheck 0, 13개 정적 페이지 | A17·A18·B09 |
| EV-C02-04 | Codex 통합 코드 검수와 보완 | PASS: 잔액 commit, lease 900초, terminal 오류, Response body 파싱, turn 재시도, DB gate fixture 보완 | A11~A17·B05 |
| EV-C02-05 | 통합 Python 비DB 선택 회귀 | PASS, 193건 | A02·A04~A06·A11~A17·B09 |
| EV-C02-06 | 통합 FE unit→lint→typecheck→webpack build | PASS: unit 42, 0 errors/15 warnings, typecheck 0, 13개 정적 페이지 | A17·A18·B09 |
| EV-C02-07 | 폐기 DB migration upgrade→downgrade→upgrade와 단일 head | PASS: 기존 profile/ledger 행과 marker 보존, `credit_operations` 재생성 | A01·A11·B03 |
| EV-C02-08 | 기존 `tests/test_credit_system.py` | PASS, 9건 | A01·A11·A13·A17 |
| EV-C02-09 | 독립 PostgreSQL 멱등·welcome 동시성·lock 분리·stale recovery | PASS, 4건 | A11·A12·A15·A16·A17 |
| EV-C02-10 | 보조 report 실패 단위 계약 | PASS: 답변 제공·report failed는 SUCCEEDED/-10C, release 미호출 | A14 |
| EV-C02-11 | Antigravity PNG 실제 크기와 note 대조 | PARTIAL 기록 금지 원칙에 따라 FAIL: desktop/recovery 일치, mobile 표기 360px이나 실제 500px | B06 |
| EV-C06-01 | 하네스 독립 재현 | PASS: 중앙이 `scripts/e2e/run_cycle06.sh`를 `6e4ebdb`에서 실행, 14/14 PASS·44 요청·외부 LLM 0회·폐기 DB 자동 삭제 | B08 |
| EV-C06-02 | 하네스 자체 테스트 | PASS: `pytest tests/e2e/test_harness_selftest.py` 25 passed (원격 DB 거부·marker·별칭·digest 검증) | B08 |
| EV-C06-03 | 브라우저 PNG 픽셀 대조 | PASS: IHDR 직접 판독 결과 1440x779·768x867·500x723로 보고값과 일치 | B06 |
| EV-C06-04 | 브라우저 대상 서버 버전 | FAIL: 8008 서버 openapi에 `/api/me/credits`·`/api/counsel/operations/{id}` 없음, 무인증 `/start` 401. 2026-09-06 적재 코드 | B06 |
| EV-C06-05 | http_trace 관측 가능성 | FAIL: `operation_status`·`credit_delta`·`operation_ref`는 해당 서버가 낼 수 없는 값 | B06 |
| EV-C06-06 | 잔액 주장과 캡처 대조 | FAIL: JSON은 시작 50C, `auth_logged_in.png`는 `잔액 확인 필요` | B06 |
| EV-C06-07 | 판정 표기 일치 | FAIL: JSON `verdicts`는 `PARTIAL`, 보고서 표와 `verdict_details`는 `NOT_RUN` | B06 |
| EV-C06-08 | 증거 민감정보 | FAIL: 텍스트 증거는 0건이나 PNG 4개에 계정 식별자와 상담 원문 노출, 보고서는 마스킹·미저장 주장 | B06 |
| EV-C06-09 | 원격 DB 쓰기 | PASS: 브라우저 대상 프로세스의 유일한 DB 연결이 `[::1]:5432` 로컬 컨테이너 | B03 |
| EV-C06-10 | 제품 코드 불변 | PASS: `bbdf758..6e4ebdb`에서 api/core/services/agents/frontend/src/migrations 변경 0 | B04 |
| EV-C06-11 | 8008 재기동 후 라우트 | PASS: openapi 9개 경로, `/api/me/credits`·`/api/counsel/operations/{id}` 존재, 무인증 `/start` 503 | B06 |
| EV-C06-12 | 런타임 게이트 상태 | PASS: `/api/public/release-gate`가 `free_beta_ready:false`와 `신뢰 anchor 미등록`을 반환, 소스 분석과 일치 | B05 |
| EV-C06-13 | `잔액 확인 필요` 근본원인 | PASS: 로컬 DB에 `credit_ledger.event_type` 부재 → `has_welcome_grant` 예외 → 503. 제품 결함 아님 | B05 |
| EV-C06-14 | 로컬 DB head 적용 | PASS: 백업(69객체) 후 `d7f4a1c2e8b9`→`e8b72c4a91d0`, profiles 3·ledger 16·sessions 25·turns 22·journal 12 전량 보존 | B03 |
| EV-C06-15 | 잔액 계약 동작 | PASS: 화면 30C = DB `credit_balance` 30, `welcome_granted` true, 조회로 인한 쓰기 0. 캡처 증거는 대기 | B09 |
| EV-C06-16 | Supabase 미접속 | PASS: C06-R2는 로컬 `iching-db`만 변경. 원격 migration 재적용·설정 변경·쓰기 0 | B03 |
| EV-C06-17 | 잔액 화면 캡처 | PASS: `balance_30c_after_local_db_head.png`(1348x866) 헤더 배지·입력 카드 모두 30C, 계정 식별자 마스킹. viewport 규격 증거는 아님 | B06 |
| EV-C06-18 | 게이트 이중 차단 | PASS: 잔액 30C(3회분)인데도 제출 버튼 비활성. `free_beta_ready:false`로 FE가 차단, BE는 503 | B05 |
| EV-C08-01 | DB 가드 반증 | PASS: 쓰기 테스트 실행 후 개발 DB 25→25 불변; 개발 DB·원격 호스트를 `TEST_DATABASE_URL`로 지정해도 차단 | B10 |
| EV-C08-02 | 폐기 DB 우회 확인 | PASS: 폐기 DB 지정 시 파괴적 테스트 13 error→0, 쓰기가 폐기 DB에 기록, 같은 시각 개발 DB 불변 | B10 |
| EV-C08-03 | 하네스 A 항목 시나리오 | PASS: 20/20, 실제 HTTP 62건. 413·422×4·CORS 200/400·무인증 200·503×2·복구 200·401/200/422/200 | B09 |
| EV-C08-04 | A36 재감지 연장 | PASS: `_has_recent_crisis` 4단계 단위 테스트. 파이프라인 미경유라 프롬프트 부재 환경에서도 실행 가능 | B09 |
| EV-C08-05 | 기계 기록 완전성 | 중앙 검수에서 FAIL 발견 후 수정: OPTIONS·바이너리 요청 5건이 `http_trace` 누락(보고 57 vs 실제 62). `record_response()` 추가로 62 일치 | B06 |
| EV-C08-06 | 카드 렌더 실질성 | PASS: 반환 PNG 10KB 초과. 빈/오류 자리표시자가 기존 단언을 통과할 수 있어 단언 추가 | B06 |
| EV-C07-01 | viewport 규격 재검증 | PASS: IHDR 직접 판독으로 1440x900·768x1024·390x844 정확 일치, DPR=1 | B06 |
| EV-C07-02 | viewport 렌더 상태 | PASS: CDP 정착 대기 3.5초 재촬영본 3장 본문 선명. 파일 크기 62/38/42KB → 91/131/70KB | B06 |
| EV-C07-03 | 390x844 리플로우 | PASS: 헤딩 3줄 줄바꿈·좌우 잘림 없음·모바일 배지 숨김. 중앙이 디바이스 에뮬레이션으로 독립 재현한 화면과 일치 | B06 |
| EV-C07-04 | 계정 식별자 마스킹 | PASS: 4/4 MASKED. 마스크 `x=876..974`가 이전 노출 글리프(`888..955`) 포함, 잔존 밝은 영역은 배지·라벨·버튼뿐 | B06 |
| EV-C07-05 | 상담 본문 마스킹 | PASS: 2/2 MASKED. `scenario_c_balance_30c.png` 하단 삐져나옴도 `y=350..776` 확장으로 해소 | B06 |
| EV-C07-06 | 정정 문구 정직성 | PASS: 잔존 `완전히 은폐함`·`완벽히 준수함` 2건은 정정 기록의 기존 문장 인용부. 실패를 전/후 대조로 보존 | B06 |
| EV-C07-07 | 금지 항목 준수 | PASS: BLK-C06-02 정정분(`cycle06_e2e_evidence.json`, `network_console_summary.json`) 재작업에서 변경 0바이트 | B04 |
| EV-C07-08 | 보고 SHA 대조 | FAIL(경미): 보고 채널의 결과 SHA가 존재하지 않는 객체. 커밋된 보고서에는 SHA 기재가 없어 저장소 기록 영향 없음 | B06 |
| EV-C03-01 | 두 소스 status·branch·시작 SHA ancestry·allowlist | PASS: clean, `83dbab4` 직접 후손, 허용 파일만 변경 | B01·B02·B04 |
| EV-C03-02 | Claude release evidence/gate/trust 독립 정·역순 | PASS: 각 252 passed | A04·B05·B09 |
| EV-C03-03 | 테스트 import 전후 runtime trust registry | PASS: 전역 주입 결함 발견 후 scoped monkeypatch와 회귀 테스트로 격리 | A04·B09 |
| EV-C03-04 | 통합 Python 선택 회귀 | PASS: 348 passed, 18 warnings; DB URL은 `127.0.0.1:1/nonexistent` | A02·A04~A06·A11~A17·B09 |
| EV-C03-05 | FE unit/helper syntax/lint/typecheck/webpack build | PASS: 42, syntax 0, lint 0 errors/15 warnings, typecheck 0, 13 routes | A05·A18·B09 |
| EV-C03-06 | Antigravity PNG hash·픽셀·표시 내용 검수 | FAIL: hash는 note와 일치하나 10개 전부 1440x779, mobile/recovery 주장 불일치 | A47·B06 |
| EV-C03-07 | E2E helper와 제품 API 계약 대조 | FAIL: public config 경로 오기(통합 수정), `/turn` 없음, `/start` payload 불일치 | A47·B05·B06 |
| EV-C03-08 | 배포 URL 읽기 전용 확인 | PASS: 관찰값 `/health` 200, 정확한 `/api/public/config` 404, Vercel `/pricing` 404 | A05 일부·B06 |
| EV-C03-09 | Supabase 메타데이터 보고 검수 | PASS: 보고상 마스킹·무쓰기, PostgreSQL 17.6, Alembic `d7f4a1c2e8b9`, T03 미적용 | B03·B06 |
| EV-C03-10 | T03 migration/RLS·가입 trigger 정적 검수 | FAIL: `credit_operations` RLS 없음, 원격 signup trigger의 WELCOME 호환 미확인 | A08·A09·A17 |
| EV-C04-01 | 원격 Supabase schema·grants·policy·function·집계 읽기 전용 조회 | PASS: PRE_T03, migration 전제 확인; 사용자 행·비밀·쓰기 없음 | A08·A09·B03 |
| EV-C04-02 | `e8b72c4` 정적 계약과 구형 seed 재생성 차단 | PASS: 43 tests | A08·A09·B09 |
| EV-C04-03 | 합성 Supabase-like PRE_T03 → head + 역할 SQL assertions | PASS: 세 테이블 RLS, client deny/own read, 제한된 server grants, 네 함수 execute 차단 | A08·A09 |
| EV-C04-04 | 합성 auth 가입 trigger | PASS: profile 1, `WELCOME` 50C 1 | A17 |
| EV-C04-05 | e8 단독 및 head→d7→head 왕복 | PASS: 권한 완화 없음, 기존 profile/ledger 3행 보존 | A01·A08·A11·B03 |
| EV-C04-06 | 합성 중복 과거 WELCOME 후보로 upgrade | PASS: 명시적 예외, migration transaction rollback | A11·A17 |
| EV-C04-07 | vanilla PostgreSQL head와 marker DB 제품 크레딧 회귀 | PASS: Supabase 객체 없이 적용, DB tests 13 passed/8 warnings | A01·A11~A17 |
| EV-C04-08 | 기존 개발 Supabase migration·실 JWT 결합 검증 | BLOCKED: 복원 지점·적용 승인 없음, 테스트 미실행 | A08·A09·A48 |
| EV-C04-09 | 전용 임시 Supabase T03+RLS, 실제 DB roles·익명 REST·Advisor | PASS: own read, client write/operation deny, anon HTTP 401, server 제한 CRUD, 공개 함수 경고 제거; Auth 발급 JWT는 NOT_RUN | A08·A09·A17 |

EV-C00-02와 EV-C00-03의 pytest 프로세스는 가드가 의도적으로 setup error를 반환해야
검사 자체가 PASS다. 제품 테스트 통과로 집계하지 않는다.

## A01~A48

| ID | 주 검증 | 담당 | 상태 | 현재 증거/차단 |
|---|---|---|---|---|
| A01 | 테스트 DB 안전 | Codex | PASS | 기존 거부 경로와 임시 `*_test` DB marker 성공 경로 모두 통과; 환경은 제거됨 |
| A02 | 기본 외부 비용 차단 | Claude Code | NOT_RUN | C08 확인분: 킬 스위치 `GENERATION_ENABLED=false`에서 start/turn 503·차감 없음·복구 200, provider allowlist, 소켓 가드. **미확인: 런타임 비용 상한이 구현돼 있지 않다**(`budget`/`quota` 제품 경로 0건) |
| A03 | 프롬프트·기준선 정직성 | Codex | NOT_RUN | 비공개 프롬프트는 worktree에 없음 |
| A04 | 출시 게이트 | Codex | PASS | runtime trust 교체 차단, release suite registry 비움, malformed fail-closed; 실제 출시 suite는 A48 BLOCKED |
| A05 | 설정·스키마 계약 | Codex | PASS | 통합 후보에서 stage·boolean·credit 엄격 파서와 기본 BE public config fail-safe 통과 |
| A06 | 인증 실패 | Codex | PASS | 실제 Auth ES256 token 200, 누락·서명 변조 401; issuer/audience/exp/sub 검증 후보 코드 사용 |
| A07 | 폐쇄 계정·구토큰 | Codex | NOT_RUN | T02/T07 필요 |
| A08 | 소유권·RLS | Codex | PASS | 개발 DB A/B role+claim, 익명 REST 401, 실제 JWT authenticated REST에서 자기 profile 1행·자기 ledger만 확인 |
| A09 | 위험 RPC·잔액 쓰기 | Codex | PASS | 개발 DB 네 함수 EXECUTE 차단·최소 grants, 실제 JWT operations 403; 쓰기 요청 없이 권한 검사 |
| A10 | 입력·본문·CORS | Claude Code | PASS | C08 하네스가 실제 HTTP로 확인: 1MB 초과 413(422 아님 = 본문 상한이 라우팅보다 먼저), 길이·패턴·필수 필드 422, CORS 허용 origin 200·허용 밖 400 |
| A11 | 정상·동시 원장 | Codex | PASS | 폐기 DB에서 비음수·append-only event·동시 직렬화와 migration 제약 확인 |
| A12 | 멱등성 | Codex | PASS | 동일 key 한 operation/최종 재생, 다른 body 409를 폐기 DB에서 확인 |
| A13 | 비과금 분기 | Codex | PASS | 위기 및 답변 미제공 pipeline 실패는 RELEASED/0C, 정상 답변은 SUCCEEDED/-10C |
| A14 | 종료·리포트 실패 | Codex | PASS | 사용자 답변 후 선택 report 실패는 정상 과금, pipeline 실패만 release |
| A15 | 내부 커밋·프로세스 종료 | Codex | PASS | 예약 commit 후 별도 session에서 credit lock 획득 가능; unit failure release 통과 |
| A16 | 복구 경합 | Codex | PASS | 만료 lease 복구와 늦은 finalize 경합이 단일 RELEASED/event/balance로 종료 |
| A17 | 웰컴·잔액 표시 | Codex | PASS | 기존 단위/DB 계약과 실제 로그인 후보 FE/API에서 복원 DB 10C 일치·조회 후 행 수 보존 |
| A18 | 공개 문서 | Codex | PASS | 통합 후보에서 단위 25·lint·typecheck·13개 페이지 webpack 프리렌더 통과 |
| A19 | 정보·동의 표현 | Codex/운영자 | BLOCKED | D01~D04 필요 |
| A20 | 라이선스·지원 | Codex | NOT_RUN | UI 존재; D13·지원 영속성 미검증 |
| A21 | 온보딩 우회 | Codex | NOT_RUN | T05 필요 |
| A22 | 선택 동의 | Codex | NOT_RUN | T05 필요 |
| A23 | 철회·버전 변경 | Codex | NOT_RUN | T05 필요 |
| A24 | 연령 정책 | Codex/운영자 | NOT_RUN | D02 개발 기준 선택; 연령 확인·우회 방지 미구현 |
| A25 | 암호화 저장 | Codex | NOT_RUN | T06 필요 |
| A26 | 키·무결성 | Codex | NOT_RUN | T06 필요 |
| A27 | 국외전송 경계 | Codex/운영자 | BLOCKED | D10 필요 |
| A28 | 안전한 이관 | Codex | NOT_RUN | T06 필요 |
| A29 | 기록 조회·삭제 | Codex | NOT_RUN | T07 필요 |
| A30 | 내보내기 | Codex | NOT_RUN | T07 필요 |
| A31 | 탈퇴 부분 실패 | Codex | NOT_RUN | T07 필요 |
| A32 | 탈퇴 중 응답 | Codex | NOT_RUN | T07 필요 |
| A33 | 보존·복원 | Codex/운영자 | BLOCKED | D04/D12 및 T07 필요 |
| A34 | AI 표시 | Codex/Antigravity | NOT_RUN | T08 필요 |
| A35 | 위기 접근성 | Claude Code/Antigravity | NOT_RUN | C08 확인분: `/api/safety/resources`가 **무인증 200**, 목록 비어 있지 않음, context 필터 200. 화면 축은 T08A 미제출. A 항목 정의가 저장소에 없어 백엔드만으로 분해 승격하지 않는다 |
| A36 | 위기 래치 | Claude Code | PASS | `agents/pipeline.py:_has_recent_crisis` + `CRISIS_LATCH_HOURS=24`. C08이 D05의 재감지 연장까지 4단계 확인(창 안 래치·만료 해제·재감지 재무장·타 사용자 미전이) |
| A37 | 카드 민감정보 | Claude Code/Antigravity | NOT_RUN | C08 확인분: 무인증 401, 인증 200 `image/png`+attachment, PNG에 tEXt/iTXt/zTXt 0개·EXIF 마커 부재·입력 문자열 미삽입, 2000자 초과 422, 미지 필드 무시. **미확인: payload 소유권 검증이 없다**(BLK-C08-01) |
| A38 | 결제 검증 | Codex | BLOCKED | D09/T09 필요 |
| A39 | 결제 이벤트 | Codex | NOT_RUN | T09 필요 |
| A40 | PG·DB 경계 | Codex | BLOCKED | provider 테스트 환경 필요 |
| A41 | 환불 계산 | Codex | NOT_RUN | D08/T10 필요 |
| A42 | 환불 동시성 | Codex | NOT_RUN | T10 필요 |
| A43 | 환불 복구 | Codex | NOT_RUN | T10 필요 |
| A44 | 환불 예외·권리 | Codex/운영자 | BLOCKED | 법률·D08/T10 필요 |
| A45 | 다중 인스턴스 제한 | Codex | NOT_RUN | T11 필요 |
| A46 | 운영 작업·권한 | Codex/운영자 | BLOCKED | D12/T11 필요 |
| A47 | E2E 회귀 | 전 도구 | **PASS (범위 한정)** | DEC-C06-01 범위 전 구성요소 통과: API 계약 E2E 14/14(중앙 독립 재현), 브라우저 인증, 브라우저 잔액, viewport 3/3(규격+렌더, C07-R1). **전체 E2E 통과가 아니다** — 브라우저 start/turn은 출시 게이트 폐쇄로 BLK-C06-05에 남아 있고 게이트 개방 시 A47 범위로 복귀한다 |
| A48 | 출시 증빙 | 전 도구/운영자 | BLOCKED | 전체 선행 작업 필요 |

## B01~B10

| ID | 주 검증 | 상태 | 현재 증거/차단 |
|---|---|---|---|
| B01 | 동일 기준점 | PASS | 원 FAIL 사유(통합 commit이 main 기반이라 단일 note만 취합)는 C06~C08에서 해소. `bbdf758 → f31d29d → 6e4ebdb → 6aadbeb → b4e54b4 → 0ec0b0c → c69b4a7 → f8beb42 → 9237c55`가 병합 커밋 0개의 선형 사슬이고 각 주기가 직전 SHA에서 분기·통합됐다 |
| B02 | 독립 worktree | PASS | 전용 `/private/tmp/iching-cycle01-integration`, `codex/cycle-05-dev-apply-e2e` 사용 |
| B03 | 실행 환경 격리 | PASS | 승인된 개발 migration 외 검사는 READ ONLY; 백업 복원 DB는 PostgreSQL 17 tmpfs, 브라우저 세션 제거 |
| B04 | 파일 소유권 | PASS | C05는 승인된 원격 migration 실행과 중앙 문서만 변경; 제품 API·FE·migration 소스 미변경 |
| B05 | 계약 일치 | PARTIAL_FIXED | C03 helper의 잘못된 payload·누락 turn·`response_snapshot` 오기를 C06 하네스가 제품 계약대로 교체하고 `E2E_CONTRACT.md`로 고정. 구 helper(`frontend/tests/e2e/mockScenarios.js`)는 아직 저장소에 남아 있다 |
| B06 | 증거 인계 | PASS | C06의 미관측 필드 기록과 50C 반증은 C07에서 제거·`inferred` 분리로, 마스킹 결함은 C07-R1에서 해소됐다. 중앙이 육안+픽셀로 교차검증했고 과장 문구도 전/후 대조로 정정됐다 |
| B07 | 독립 검수 | PASS | Antigravity가 설정·브라우저를 직접 재현, Claude가 문서·코드 계약을 검수, Codex가 두 증거를 교차검수 |
| B08 | 통합 재현 | PASS | 고정 SQL SHA, 암호화 백업 복원, head·행 수·역할 검증 절차 기록; 개발 migration 재적용 금지 |
| B09 | 결합 회귀 | PASS | 실제 ES256 후보 인증, authenticated REST RLS, 동일 FE 소스+후보 API+head 복원 DB 잔액 결합 통과 |
| B10 | 권한 경계 | PASS | C08 묶음 0이 DB 가드를 fixture opt-in에서 기본 차단으로 전환(`tests/conftest.py`). 반증 3회 모두 차단: 쓰기 시도 후 개발 DB 불변, 개발 DB 지정 거부, 원격 호스트 거부. 폐기 DB 지정 시에만 열리고 쓰기가 그쪽으로 간다 |

## 다음 검증

1. C05의 백업·복원·개발 DB 적용은 완료됐으므로 반복 적용하지 않는다.
2. Auth leaked-password protection과 public extension/default ACL은 별도 운영 보안 카드로 다룬다.
3. 실제 E2E harness는 C06에서 구축됐다(`scripts/e2e/run_cycle06.sh`). 재구축하지 않는다.
4. 8008 재기동·로컬 DB head·잔액 캡처는 C06-R2/R3에서 완료됐다.
5. A47은 C07-R1에서 범위 한정 PASS가 됐다. 전체 E2E 통과로 읽지 않는다.
6. 브라우저 start/turn은 BLK-C06-05로 이월됐다. 게이트가 정상 경로로 열린 뒤 수행하며,
   우회나 인수증거 위조로 닫지 않는다.
7. BLK-C06-02·BLK-C06-04는 C07/C07-R1에서 해소됐다.
8. 구 helper `frontend/tests/e2e/mockScenarios.js` 폐기 여부를 결정한다(제품 경로 판단 필요).
9. 기본 3000과 명시적 3005 외 자동 증가 포트는 OAuth 지원 대상으로 간주하지 않는다.
