# -*- coding: utf-8 -*-
"""하네스 자체 테스트. DB도 docker도 네트워크도 필요 없다.

하네스가 틀리면 제품 판정도 틀린다. 안전 가드·별칭·비밀 제거·토큰 발급은
하네스의 주장을 떠받치는 부분이라 따로 검증한다.
"""

import jwt
import pytest

from tests.e2e.harness import fake_pipeline, ports, recorder, safety, tokens


# --- 안전 가드 ---------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+asyncpg://u:p@db.sample-project-ref.supabase.co:5432/postgres",
        "postgresql+asyncpg://u:p@aws-0-ap-northeast-2.pooler.supabase.com:6543/postgres",
        "postgresql+asyncpg://u:p@some-host.amazonaws.com:5432/prod_test",
    ],
)
def test_remote_database_urls_are_rejected(url):
    """원격 관리형 DB는 이름이 맞아도 거부한다."""
    assert safety.database_url_problems(url)


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+asyncpg://u:p@127.0.0.1:5432/iching",       # _test 아님
        "postgresql+asyncpg://u:p@127.0.0.1:5432/production",   # _test 아님
        "sqlite+aiosqlite:///./local_test.db",                  # PostgreSQL 아님
        "",
    ],
)
def test_unsafe_local_urls_are_rejected(url):
    assert safety.database_url_problems(url)


def test_disposable_local_url_is_accepted():
    assert safety.database_url_problems(
        "postgresql+asyncpg://u:p@127.0.0.1:15432/iching_e2e_test"
    ) == []


def test_supabase_url_local_only_by_default():
    assert safety.supabase_url_problems(
        "https://sample-project-ref.supabase.co", allow_remote_jwks=False
    )
    assert safety.supabase_url_problems(
        "http://127.0.0.1:18000", allow_remote_jwks=False
    ) == []
    # 브라우저 모드에서만 원격 JWKS를 허용한다 (읽기 전용, DB와 무관).
    assert safety.supabase_url_problems(
        "https://sample-project-ref.supabase.co", allow_remote_jwks=True
    ) == []


def test_assert_safe_or_die_raises_on_problems():
    with pytest.raises(SystemExit):
        safety.assert_safe_or_die(["문제"], "TEST")


# --- 포트 -------------------------------------------------------------------


def test_reserved_ports_are_never_allocated():
    """사용자 프로세스가 쓰는 포트를 하네스가 가져가지 않는다."""
    for _ in range(5):
        port = ports.find_free_port(3000)
        assert port not in ports.RESERVED_PORTS


def test_find_free_ports_returns_distinct_ports():
    allocated = ports.find_free_ports(3, 18100)
    assert len(set(allocated)) == 3


# --- 토큰 -------------------------------------------------------------------


def test_minted_token_carries_product_required_claims():
    """`api.deps.require_user`가 요구하는 클레임을 실제로 담는지."""
    secret = tokens.new_secret()
    issuer = tokens.issuer_for("http://127.0.0.1:18000")
    subject = tokens.new_user_id()
    claims = jwt.decode(
        tokens.mint(secret=secret, issuer=issuer, subject=subject),
        secret,
        algorithms=["HS256"],
        audience="authenticated",
        issuer=issuer,
        options={"require": ["exp", "sub", "iss"]},
    )
    assert claims["sub"] == subject


def test_issuer_matches_product_rule():
    from api.deps import expected_issuer
    from core.config import settings

    assert tokens.issuer_for(settings.SUPABASE_URL) == expected_issuer()


def test_expired_token_fails_verification():
    secret = tokens.new_secret()
    issuer = tokens.issuer_for("http://127.0.0.1:18000")
    token = tokens.mint_expired(secret=secret, issuer=issuer, subject=tokens.new_user_id())
    with pytest.raises(jwt.PyJWTError):
        jwt.decode(token, secret, algorithms=["HS256"], audience="authenticated",
                   issuer=issuer)


def test_idempotency_key_matches_product_pattern():
    from services.credit_operation_service import validate_idempotency_key

    for ref in ("S01", "S13-final", "a"):
        key = tokens.idempotency_key("e2e" + ref)
        assert validate_idempotency_key(key) == key


# --- 보고서 비밀 제거 ---------------------------------------------------------


def test_uuid_values_never_reach_the_report():
    report = recorder.Report(run_sha="0" * 40)
    scenario = report.scenario("T01", "별칭 치환")
    raw = "3f2b9c1e-4a5d-4f6b-8c7d-9e0f1a2b3c4d"
    scenario.check("same_operation", raw, raw)
    rendered = repr(report.to_dict())
    assert raw not in rendered
    assert scenario.assertions[0]["ok"] is True


def test_jwt_and_database_url_are_redacted():
    report = recorder.Report(run_sha="0" * 40)
    scenario = report.scenario("T02", "비밀 제거")
    scenario.check("token", "eyJhbGciOi.eyJzdWIiOi.c2lnbmF0dXJl", "x")
    scenario.check("db", "postgresql+asyncpg://u:secret@127.0.0.1:15432/x_test", "y")
    rendered = repr(report.to_dict())
    assert "eyJhbGciOi" not in rendered
    assert "secret@" not in rendered


def test_opaque_check_hides_content_but_keeps_verdict():
    report = recorder.Report(run_sha="0" * 40)
    scenario = report.scenario("T03", "본문 비노출")
    text = "상담 본문처럼 취급해야 하는 긴 문자열"
    assert scenario.check_opaque("same", text, text) is True
    assert scenario.check_opaque("diff", text, text + "!") is False
    rendered = repr(report.to_dict())
    assert text not in rendered
    assert "sha256:" in rendered


def test_safe_body_drops_unlisted_fields():
    body = recorder.safe_body(
        {
            "operation_status": "SUCCEEDED",
            "user_facing_message": "상담 본문",
            "session_id": "3f2b9c1e-4a5d-4f6b-8c7d-9e0f1a2b3c4d",
            "credit_delta": -10,
        }
    )
    assert body["operation_status"] == "SUCCEEDED"
    assert body["credit_delta"] == -10
    assert "user_facing_message" not in body
    assert "session_id" not in body
    # 필드 이름 목록은 계약 검증에 쓰므로 남긴다. 값은 남기지 않는다.
    assert "user_facing_message" in body["_field_names"]


def test_report_verdict_reflects_failures():
    report = recorder.Report(run_sha="0" * 40)
    ok = report.scenario("T04", "통과")
    ok.check("x", 1, 1)
    ok.finish()
    assert report.verdict() == "HARNESS_READY"

    bad = report.scenario("T05", "실패")
    bad.check("y", 1, 2)
    bad.finish()
    assert report.verdict() == "NEEDS_FIX"
    assert bad.result == "FAIL"


# --- fake 파이프라인 ---------------------------------------------------------


def test_fake_returns_product_turn_result_fields():
    """필드 이름을 하네스가 지어내지 않았는지 제품 dataclass로 확인한다."""
    import dataclasses

    from agents.pipeline import TurnResult

    names = {f.name for f in dataclasses.fields(TurnResult)}
    for required in (
        "session_id", "turn_number", "user_facing_message", "needs_followup",
        "is_final", "safety_category", "journal_summary", "evidences",
    ):
        assert required in names


def test_fake_messages_are_deterministic():
    first = fake_pipeline._message_for(2, False)
    second = fake_pipeline._message_for(2, False)
    assert first == second
    assert fake_pipeline._message_for(3, True) != first


def test_fake_block_signals_round_trip():
    fake_pipeline.reset()
    user = tokens.new_user_id()
    fake_pipeline.arm_block(user)
    assert fake_pipeline.BEHAVIORS[user] == "block"
    assert fake_pipeline.wait_until_entered(user, timeout=0.01) is False
    fake_pipeline.ENTERED[user].set()
    assert fake_pipeline.wait_until_entered(user, timeout=0.01) is True
    fake_pipeline.release_block(user)
    assert fake_pipeline.RELEASE[user].is_set()
    fake_pipeline.reset()
    assert fake_pipeline.BEHAVIORS == {}


def test_fake_pipeline_imports_no_llm_provider():
    """fake 모듈이 외부 LLM SDK를 끌어오지 않는지."""
    import inspect

    source = inspect.getsource(fake_pipeline)
    for banned in ("anthropic", "google.genai", "openai", "ollama", "vertexai", "httpx"):
        assert banned not in source
