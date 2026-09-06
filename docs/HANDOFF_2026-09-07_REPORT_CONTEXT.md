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

- 로컬 커밋: `8c60c34 Persist report context across counsel turns`
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

   로컬 커밋 `8c60c34`는 아직 원격 push 여부를 확인하지 못했다. `git status -sb`, `git log -1`, `git remote -v`를 확인한 뒤 필요하면 push한다. 이 인계 문서도 별도 커밋에 포함한다.

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
- `prompts/report.md`는 기존 ignore 규칙에 걸려 `git add -f`로 처음 추적했다. 이후 수정은 추적 파일이므로 일반 `git add`가 가능하다.
