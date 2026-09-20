"""site visit analytics for the operator dashboard

Revision ID: e5a3c91d7b48
Revises: c08b01a7f39d
Create Date: 2026-09-18 10:20:00.000000

운영 대시보드의 방문자수·재방문 횟수 지표를 위한 자체 1st-party 방문 로그.

Vercel Web Analytics는 우리 DB에 아무 것도 남기지 않고, "방문자별 재방문 횟수"
라는 지표 자체를 제공하지 않는다. 그래서 방문 이벤트를 직접 적재한다.

수집 최소화 원칙:
- IP 주소와 User-Agent 원문은 저장하지 않는다. 기기 구분은 mobile/desktop/tablet
  세 값으로만 좁힌다.
- 방문자 식별자는 원문을 저장하지 않고 서버 pepper를 섞은 SHA-256 해시로
  가명처리하여 남긴다(services/visit_analytics_service.py의 hash_visitor_id 참고).
  pepper와 브라우저 식별자가 결합되면 재계산이 가능하므로 익명화가 아닌 가명정보에 해당한다.
- referrer는 host만 남긴다. path와 query string은 버린다.
- 회원 연결(user_id)은 ON DELETE SET NULL이다. 탈퇴 시 해당 계정과 연결된 모든
  visitor_hash 기준 방문 행을 삭제하여 과거 이력 재연결을 차단한다(api/routers/account.py).

visit_index는 그 방문자의 n번째 방문이다. 서버가 계산해서 박아두기 때문에
재방문 분포 집계에서 윈도우 함수를 다시 돌리지 않아도 된다.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "e5a3c91d7b48"
down_revision: Union[str, Sequence[str], None] = "c08b01a7f39d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.site_visits (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            visitor_hash TEXT NOT NULL,
            visit_index INTEGER NOT NULL,
            user_id UUID NULL REFERENCES public.profiles(id) ON DELETE SET NULL,
            entry_path TEXT NULL,
            referrer_host TEXT NULL,
            device TEXT NULL,
            started_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    # 기간별 집계(오늘/7일/30일/14일 추이)가 전부 started_at 범위 스캔이다.
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_site_visits_started_at
            ON public.site_visits (started_at DESC)
        """
    )
    # 방문 기록 시 같은 방문자의 마지막 방문을 한 건 찾아온다(세션 병합 판정).
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_site_visits_visitor_hash_started_at
            ON public.site_visits (visitor_hash, started_at DESC)
        """
    )

    # RLS 및 Role Grants — f4b1e8a92c3d의 패턴을 따른다.
    # anon/authenticated의 직접 접근을 차단한다. 방문 적재도 서버(service_role)를
    # 거쳐야 한다. 브라우저가 이 테이블에 직접 INSERT할 수 있으면 visit_index를
    # 조작해 재방문 지표를 원하는 값으로 만들 수 있다.
    op.execute("ALTER TABLE public.site_visits ENABLE ROW LEVEL SECURITY")
    op.execute("REVOKE ALL PRIVILEGES ON TABLE public.site_visits FROM PUBLIC")
    op.execute(
        """
        DO $roles$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                REVOKE ALL PRIVILEGES ON TABLE public.site_visits FROM anon;
            END IF;

            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
                REVOKE ALL PRIVILEGES ON TABLE public.site_visits FROM authenticated;
            END IF;

            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
                REVOKE ALL PRIVILEGES ON TABLE public.site_visits FROM service_role;
                -- UPDATE는 탈퇴 시 user_id 분리, DELETE는 보존기간 경과분 파기용이다.
                GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.site_visits TO service_role;
            END IF;
        END
        $roles$;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.site_visits CASCADE")
