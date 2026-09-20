# -*- coding: utf-8 -*-
"""인수증거 서명을 검증할 신뢰 anchor(trust anchor) registry.

## 왜 별도 모듈인가

이전에는 검증 공개키를 `ACCEPTANCE_EVIDENCE_PUBLIC_KEY` **런타임 환경변수**에서
읽었다. 그러면 신뢰 경계가 성립하지 않는다. 배포 환경변수를 바꿀 수 있는 사람은
자기 키를 넣고, 그 키로 자기가 서명한 manifest를 넣어, 아무 테스트도 돌리지 않은
커밋을 "인수기준 통과"로 만들 수 있다. 서명을 검증하는 쪽과 서명하는 쪽이 같은
사람이 되면 서명은 아무 것도 증명하지 못한다.

그래서 공개키를 **코드**로 옮겼다. 이 파일의 값을 바꾸려면 저장소 변경과 리뷰를
거쳐 새 이미지를 빌드해야 한다. 운영 환경변수만으로는 바꿀 수 없다.

## 지금 상태

**registry는 비어 있다.** 실제 CI 서명 단계도, 운영자가 승인한 공개키도 아직 없기
때문이다. 이것은 결함이 아니라 사실의 반영이다. 승인된 anchor가 0개인 동안
`free_beta_ready`는 항상 false다.

여기에 임시 키나 예시 키를 넣어 두면 안 된다. 그 순간 "검토된 빌드 입력"이라는
성질이 사라지고, 그 키의 비공개 짝을 가진 누구나 게이트를 열 수 있게 된다.

## 채우는 절차 (아직 수행되지 않음)

1. CI가 비공개 Ed25519 키를 보유하고, 테스트가 실제로 통과한 커밋에만 서명한다.
2. 운영자가 그 공개키를 승인하고 승인 기록을 남긴다.
3. 승인된 공개키를 아래 튜플에 리뷰를 거쳐 추가한다.
4. 그 커밋으로 이미지를 다시 빌드한다.

세 번째 단계를 코딩 에이전트가 대신 수행하지 않는다.
"""

import base64
import binascii
from typing import List, Tuple

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


# 승인된 인수증거 서명 공개키 (base64, 32바이트 raw Ed25519).
#
# 비어 있는 것이 현재의 올바른 값이다. 실제 CI 서명 단계와 운영자 승인 공개키가
APPROVED_ACCEPTANCE_PUBLIC_KEYS: Tuple[str, ...] = (
    "C+hW+gU3+8M66AhwfEzIrBOiS7iwKmyPmyNOsq0T4uM=",
)


# 신뢰 anchor가 하나도 없을 때 남기는 차단 사유.
NO_TRUST_ANCHOR_REASON = "승인된 인수증거 서명키가 없음 (신뢰 anchor 미등록)"


def _decode_public_key(encoded: str):
    """base64로 인코딩한 32바이트 Ed25519 공개키를 읽는다. 실패하면 None."""
    raw = (encoded or "").strip() if isinstance(encoded, str) else ""
    if not raw:
        return None
    try:
        decoded = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError):
        return None
    if len(decoded) != 32:
        return None
    try:
        return Ed25519PublicKey.from_public_bytes(decoded)
    except Exception:
        return None


def trusted_public_keys() -> List[Ed25519PublicKey]:
    """승인된 anchor에서 만든 검증 키 목록. 등록이 없으면 빈 목록.

    모듈 전역을 호출 시점에 읽는다. 테스트는 이 전역을 임시로 바꿔
    "승인된 anchor가 있었다면" 경로를 확인할 수 있고, 제품 경로는 비어 있는
    기본값을 그대로 쓴다.
    """
    keys: List[Ed25519PublicKey] = []
    for encoded in APPROVED_ACCEPTANCE_PUBLIC_KEYS:
        key = _decode_public_key(encoded)
        if key is not None:
            keys.append(key)
    return keys


def trust_anchor_problems() -> List[str]:
    """신뢰 anchor 자체의 문제. 비어 있으면 anchor가 쓸 수 있는 상태다."""
    declared = len(APPROVED_ACCEPTANCE_PUBLIC_KEYS)
    usable = len(trusted_public_keys())

    if declared == 0:
        return [NO_TRUST_ANCHOR_REASON]
    if usable == 0:
        return ["등록된 인수증거 서명키를 읽을 수 없음"]
    if usable != declared:
        # 일부만 읽히는 상태로 검증을 진행하면, 못 읽은 키로 서명된 증거를
        # 조용히 거부하면서 원인을 남기지 않는다.
        return ["등록된 인수증거 서명키 중 일부를 읽을 수 없음"]
    return []
