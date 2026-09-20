"""인증 경계 하드닝 테스트 (T02-BE 1단계).

인수기준 A06(미인증·만료·변조·타 프로젝트 iss·운영 dev-token은 차감/LLM 이전 거부)과
A10(카드 입력 검증) 중 DB에 의존하지 않는 범위를 검증한다.

RLS와 계정 상태 확인(A07, A08)은 전용 PostgreSQL과 account_state 스키마가 필요해
여기서 다루지 않는다. schema-ownership-v1 합의 이후 T02-BE 2단계에서 한다.
"""

import time

import jwt
import pytest
from fastapi import HTTPException

from api import deps
from core.config import settings


@pytest.fixture(autouse=True)
def reset_rate_limit_state():
    """레이트리미터가 프로세스 전역이라 테스트마다 비운다."""
    deps._request_records.clear()
    deps._user_records.clear()
    yield
    deps._request_records.clear()
    deps._user_records.clear()


@pytest.fixture
def restore_settings():
    saved = {
        "DEV_AUTH_BYPASS_ENABLED": settings.DEV_AUTH_BYPASS_ENABLED,
        "ENVIRONMENT": settings.ENVIRONMENT,
        "USER_RATE_LIMIT_PER_MINUTE": settings.USER_RATE_LIMIT_PER_MINUTE,
    }
    yield settings
    for key, value in saved.items():
        setattr(settings, key, value)


class FakeRequest:
    """require_user / check_rate_limit이 쓰는 부분만 흉내 낸다."""

    class _Client:
        def __init__(self, host):
            self.host = host

    class _State:
        pass

    def __init__(self, authorization: str = "", host: str = "1.2.3.4"):
        self.headers = {"authorization": authorization} if authorization else {}
        self.client = self._Client(host)
        self.state = self._State()


def make_token(secret: str, *, issuer=None, sub="user-1", audience="authenticated", exp_delta=600):
    payload = {"sub": sub, "aud": audience, "exp": int(time.time()) + exp_delta}
    if issuer is not None:
        payload["iss"] = issuer
    return jwt.encode(payload, secret, algorithm="HS256")


# --- dev-token fail-closed ---


@pytest.mark.asyncio
async def test_dev_token_rejected_when_bypass_disabled(restore_settings):
    """기본값(우회 꺼짐)에서는 개발 환경이어도 dev-token이 통하지 않는다.

    예전에는 ENVIRONMENT != "production" 하나로 열렸고, 그 기본값이
    "development"라 환경변수가 빠진 배포에서 우회가 살아 있었다.
    """
    restore_settings.DEV_AUTH_BYPASS_ENABLED = False
    restore_settings.ENVIRONMENT = "development"

    with pytest.raises(HTTPException) as exc:
        await deps.require_user(FakeRequest("Bearer dev-token"))
    assert exc.value.status_code in (401, 500)


@pytest.mark.asyncio
async def test_dev_token_allowed_only_with_explicit_optin(restore_settings):
    restore_settings.DEV_AUTH_BYPASS_ENABLED = True
    restore_settings.ENVIRONMENT = "development"

    user_id = await deps.require_user(FakeRequest("Bearer dev-token"))
    assert user_id == "00000000-0000-0000-0000-000000000000"


@pytest.mark.asyncio
async def test_dev_token_never_allowed_in_production(restore_settings):
    """우회를 켜 두고 운영으로 올려도 열리지 않아야 한다 (이중 조건)."""
    restore_settings.DEV_AUTH_BYPASS_ENABLED = True
    restore_settings.ENVIRONMENT = "production"

    with pytest.raises(HTTPException) as exc:
        await deps.require_user(FakeRequest("Bearer dev-token"))
    assert exc.value.status_code in (401, 500)


# --- 발급자(iss) 검증 ---


def test_expected_issuer_derived_from_supabase_url():
    assert deps.expected_issuer() == f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1"


@pytest.mark.asyncio
async def test_token_without_issuer_is_rejected(restore_settings):
    """iss가 없으면 거부한다. 기존에는 iss를 아예 보지 않았다."""
    restore_settings.DEV_AUTH_BYPASS_ENABLED = False
    secret = settings.SUPABASE_JWT_SECRET or "test-secret"
    settings.SUPABASE_JWT_SECRET = secret

    token = make_token(secret, issuer=None)
    with pytest.raises(HTTPException) as exc:
        await deps.require_user(FakeRequest(f"Bearer {token}"))
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_token_from_other_project_is_rejected(restore_settings):
    """다른 Supabase 프로젝트가 발급한 형태의 토큰은 거부한다."""
    restore_settings.DEV_AUTH_BYPASS_ENABLED = False
    secret = settings.SUPABASE_JWT_SECRET or "test-secret"
    settings.SUPABASE_JWT_SECRET = secret

    token = make_token(secret, issuer="https://attacker.supabase.co/auth/v1")
    with pytest.raises(HTTPException) as exc:
        await deps.require_user(FakeRequest(f"Bearer {token}"))
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_valid_token_with_correct_issuer_passes(restore_settings):
    restore_settings.DEV_AUTH_BYPASS_ENABLED = False
    secret = settings.SUPABASE_JWT_SECRET or "test-secret"
    settings.SUPABASE_JWT_SECRET = secret

    token = make_token(secret, issuer=deps.expected_issuer(), sub="user-abc")
    request = FakeRequest(f"Bearer {token}")
    assert await deps.require_user(request) == "user-abc"
    # 이후 단계가 재검증 없이 쓸 수 있게 남긴다.
    assert request.state.user_id == "user-abc"


# --- 레이트리미터 ---


@pytest.mark.asyncio
async def test_pre_auth_limit_does_not_key_on_raw_header():
    """토큰 원문이 딕셔너리 키로 들어가지 않는다."""
    long_token = "Bearer " + ("A" * 5000)
    await deps.check_rate_limit(FakeRequest(long_token))

    assert long_token not in deps._request_records
    key = next(iter(deps._request_records))
    assert key.startswith("t:")
    assert len(key) <= 40


@pytest.mark.asyncio
async def test_pre_auth_limit_falls_back_to_ip():
    await deps.check_rate_limit(FakeRequest("", host="9.9.9.9"))
    assert "ip:9.9.9.9" in deps._request_records


@pytest.mark.asyncio
async def test_pre_auth_limit_blocks_after_threshold():
    request = FakeRequest("", host="5.5.5.5")
    for _ in range(deps._RATE_LIMIT_MAX_REQUESTS):
        await deps.check_rate_limit(request)

    with pytest.raises(HTTPException) as exc:
        await deps.check_rate_limit(request)
    assert exc.value.status_code == 429
    assert exc.value.headers.get("Retry-After")


def test_user_limit_survives_token_rotation(restore_settings):
    """토큰을 새로 발급받아도 사용자 카운터는 이어진다.

    예전에는 Authorization 헤더가 키였기 때문에 토큰만 갱신하면 한도가
    초기화됐다.
    """
    restore_settings.USER_RATE_LIMIT_PER_MINUTE = 3
    for _ in range(3):
        deps._enforce_user_rate_limit("same-user")

    with pytest.raises(HTTPException) as exc:
        deps._enforce_user_rate_limit("same-user")
    assert exc.value.status_code == 429

    # 다른 사용자는 영향받지 않는다.
    deps._enforce_user_rate_limit("other-user")


def test_user_and_client_stores_are_separate():
    deps._enforce_user_rate_limit("u1")
    assert "u:u1" in deps._user_records
    assert "u:u1" not in deps._request_records


# --- 카드 입력 검증 (A10 일부) ---


def test_card_data_caps_text_length():
    from api.routers.card import CardData

    with pytest.raises(Exception):
        CardData(client_action_pledge="가" * 5000)


def test_card_data_caps_list_length():
    from api.routers.card import CardData

    with pytest.raises(Exception):
        CardData(inner_coping_strategies=["항목"] * 50)


def test_card_data_truncates_list_items():
    from api.routers.card import CardData

    data = CardData(inner_coping_strategies=["나" * 1000]).to_renderer_dict()
    assert len(data["inner_coping_strategies"][0]) == 300


def test_card_data_omits_unset_fields_so_renderer_defaults_apply():
    """미지정 필드를 None으로 넘기면 렌더러의 기존 기본 문구가 죽는다."""
    from api.routers.card import CardData

    data = CardData(is_crisis=True).to_renderer_dict()
    assert data == {"is_crisis": True}


def test_card_data_ignores_unknown_fields():
    """서버 생성 payload에 모르는 키가 있어도 카드 저장이 깨지지 않는다."""
    from api.routers.card import CardData

    data = CardData(sacred_metaphor="바람", unknown_future_field="x").to_renderer_dict()
    assert data == {"is_crisis": False, "sacred_metaphor": "바람"}


# --- CYCLE-00-R2: 상담 API 게이트 연결 (P1-1) ---

from fastapi.testclient import TestClient

from core.release_gate import FREE_BETA_REQUIRED_DECISIONS


def _app_client():
    import api.main as api_main

    return TestClient(api_main.app)


ALL_FREE_BETA = ",".join(FREE_BETA_REQUIRED_DECISIONS)

_START = ("/api/counsel/start", {"question": "테스트 질문"})
_TURN = ("/api/counsel/turn", {"session_id": "abc123", "user_message": "테스트"})


# 형식상 유효한 증거 한 벌. 합성값이며 실제 승인값이 아니다.
_EVIDENCE_FIELDS = (
    "LEGAL_DOCUMENTS_VERSION",
    "LEGAL_DOCUMENTS_PUBLISHED",
    "FREE_BETA_LAUNCH_APPROVED_BY",
    "FREE_BETA_LAUNCH_APPROVED_AT",
    "ACCEPTANCE_EVIDENCE_SHA",
    "ACCEPTANCE_EVIDENCE_SUITE_VERSION",
    "ACCEPTANCE_MANIFEST_PATH",
    "ACCEPTANCE_EVIDENCE_PUBLIC_KEY",
    "BUILD_GIT_SHA",
)
# 서명된 manifest까지 포함한 증거 한 벌은 test_release_gate가 만든 임시 자료를
# 재사용한다. 실제 CI 키도 운영 증거도 아니다. 신뢰 registry는 import 시점이
# 아니라 아래 fixture 범위에서만 열어 테스트 수집 순서가 제품 판정을 바꾸지 않게 한다.
from tests.test_release_gate import (
    TEST_RELEASE_PUBLIC_KEY as _TEST_RELEASE_PUBLIC_KEY,
    TEST_RELEASE_SUITE as _TEST_RELEASE_SUITE,
    VALID_EVIDENCE as _VALID_EVIDENCE,
)
from core import release_evidence, release_trust


@pytest.fixture
def gate_settings(monkeypatch):
    monkeypatch.setattr(
        release_trust,
        "APPROVED_ACCEPTANCE_PUBLIC_KEYS",
        (_TEST_RELEASE_PUBLIC_KEY,),
    )
    monkeypatch.setattr(
        release_evidence,
        "RELEASE_ELIGIBLE_SUITE_VERSIONS",
        frozenset({_TEST_RELEASE_SUITE}),
    )
    monkeypatch.setattr(
        release_evidence,
        "KNOWN_SUITE_VERSIONS",
        frozenset(
            release_evidence.KNOWN_SUITE_VERSIONS | {_TEST_RELEASE_SUITE}
        ),
    )
    tracked = (
        "OPERATOR_ATTESTED_DECISIONS",
        "GENERATION_ENABLED",
        "SERVICE_STAGE",
    ) + _EVIDENCE_FIELDS
    saved = {name: getattr(settings, name) for name in tracked}
    yield settings
    for name, value in saved.items():
        setattr(settings, name, value)


def _open_free_beta_gate():
    """D 표시와 증거를 모두 채워 무료 베타 게이트를 연다."""
    settings.OPERATOR_ATTESTED_DECISIONS = ALL_FREE_BETA
    for name, value in _VALID_EVIDENCE.items():
        setattr(settings, name, value)


def _clear_free_beta_evidence():
    for name in _EVIDENCE_FIELDS:
        setattr(settings, name, False if name.endswith("PUBLISHED") else "")


@pytest.mark.parametrize("path,body", [_START, _TURN])
def test_unready_free_beta_blocks_consultation(gate_settings, path, body):
    """P1-1: free_beta_ready=false인데 킬 스위치가 켜져 있으면 503이어야 한다.

    이전에는 이 조합에서 인증·DB·LLM 경로로 그대로 진행했다.
    """
    gate_settings.OPERATOR_ATTESTED_DECISIONS = ""
    _clear_free_beta_evidence()
    gate_settings.GENERATION_ENABLED = True

    res = _app_client().post(path, json=body)
    assert res.status_code == 503
    assert "출시 준비" in res.json()["detail"]


@pytest.mark.parametrize("path,body", [_START, _TURN])
def test_ready_free_beta_proceeds_to_next_dependency(gate_settings, path, body):
    """게이트가 열리면 다음 의존성(인증)으로 넘어간다. 인증이 없으므로 401이다."""
    _open_free_beta_gate()
    gate_settings.GENERATION_ENABLED = True

    res = _app_client().post(path, json=body)
    assert res.status_code == 401


@pytest.mark.parametrize("path,body", [_START, _TURN])
def test_kill_switch_blocks_even_when_ready(gate_settings, path, body):
    """킬 스위치는 출시 준비 여부와 무관하게 막는다."""
    _open_free_beta_gate()
    gate_settings.GENERATION_ENABLED = False

    res = _app_client().post(path, json=body)
    assert res.status_code == 503
    assert "일시 중단" in res.json()["detail"]


@pytest.mark.parametrize("path,body", [_START, _TURN])
def test_gate_and_kill_switch_give_distinguishable_reasons(gate_settings, path, body):
    """둘 다 503이지만 이유가 구분돼야 한다. 합치면 장애 대응과 미준비를 못 가른다."""
    gate_settings.GENERATION_ENABLED = True
    gate_settings.OPERATOR_ATTESTED_DECISIONS = ""
    _clear_free_beta_evidence()
    unready = _app_client().post(path, json=body).json()["detail"]

    _open_free_beta_gate()
    gate_settings.GENERATION_ENABLED = False
    killed = _app_client().post(path, json=body).json()["detail"]

    assert unready != killed
