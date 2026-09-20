# Supabase DB 스키마 & RLS 설계

`docs/DEPLOYMENT_AND_MONETIZATION_BLUEPRINT.md`에서 분리해 온 문서다. 원 문서에는
가격·원가 등 대외 공개 대상이 아닌 내용이 함께 있어 리포지토리에서 제외했고,
스키마는 운영 문서들이 참조하므로 여기 남긴다.

`profiles`·`credit_ledger`·`credit_operations`는 크레딧 경계이며 스키마의
유일한 소유자는 Alembic(`migrations/`)이다. 이 문서와 production seed는 복사해
실행하는 DDL 출처가 아니다.

## 현행 계약

- `c3a91f4d6b27`이 멱등 operation·원장 계약과 `WELCOME` event identity를 만든다.
- `e8b72c4a91d0`이 세 크레딧 테이블의 RLS와 최소 권한을 고정한다.
- `authenticated`는 자신의 profile·ledger만 읽고 크레딧 쓰기와
  `credit_operations` 직접 접근을 하지 못한다. `anon`은 세 테이블에 접근하지 못한다.
- 백엔드 DB 연결만 profile·ledger·operation을 계약된 범위에서 쓴다.
- 가입 트리거는 정확히 한 번 `WELCOME` 50C를 남기고 `search_path`를
  `pg_catalog`으로 고정한다. 모호한 기존 웰컴 행은 migration을 중단시킨다.
- 구형 `deduct_credit` RPC는 애플리케이션 계약이 아니며 Data API 실행 권한을
  주지 않는다. 차감은 백엔드 operation service가 소유한다.

## 적용 경계

Supabase에는 `alembic upgrade head`로만 적용한다. 적용 전에 백업·복원 지점과
대상 프로젝트를 확정하고, 적용 후에 `anon`·`authenticated` 거부와 서버 경로
성공을 역할별로 검증한다. migration이 통과했다는 사실만으로 출시나 RLS
`VERIFIED`로 올리지 않는다.

---
