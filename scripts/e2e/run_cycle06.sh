#!/usr/bin/env bash
# CYCLE-06 E2E 하네스 단일 실행 명령.
#
#   scripts/e2e/run_cycle06.sh                 # API 시나리오만 (기본)
#   scripts/e2e/run_cycle06.sh --with-frontend # 브라우저 검증용으로 FE까지 기동
#
# 이 스크립트는 사용자 프로세스를 죽이지 않는다. 3005·8008·5432가 이미 쓰이고
# 있어도 그대로 두고, 비어 있는 고유 포트를 새로 받는다.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${REPO_ROOT}"

VENV_PYTHON="${E2E_PYTHON:-}"
if [[ -z "${VENV_PYTHON}" ]]; then
  # git worktree에서 실행하면 .venv는 주 체크아웃에 있다. 상위로 올라가며 찾는다.
  probe="${REPO_ROOT}"
  for _ in 1 2 3 4 5 6; do
    if [[ -x "${probe}/.venv/bin/python" ]]; then
      VENV_PYTHON="${probe}/.venv/bin/python"
      break
    fi
    probe="$(dirname "${probe}")"
    [[ "${probe}" == "/" ]] && break
  done
fi

if [[ -z "${VENV_PYTHON}" || ! -x "${VENV_PYTHON}" ]]; then
  echo "[E2E-ABORT] Python 가상환경을 찾지 못했습니다." >&2
  echo "            E2E_PYTHON=/path/to/.venv/bin/python 로 지정하십시오." >&2
  exit 4
fi

if ! docker version >/dev/null 2>&1; then
  echo "[E2E-BLOCKED] docker 데몬에 연결할 수 없습니다." >&2
  echo "              Docker Desktop을 켠 뒤 다시 실행하십시오." >&2
  echo "              원격 Supabase로 대체하지 마십시오." >&2
  exit 3
fi

OUT_DIR="${E2E_OUT_DIR:-${TMPDIR:-/tmp}/iching-e2e-cycle06}"
mkdir -p "${OUT_DIR}"

echo "[E2E] repo      : ${REPO_ROOT}"
echo "[E2E] python    : ${VENV_PYTHON}"
echo "[E2E] sha       : $(git rev-parse HEAD)"
echo "[E2E] out       : ${OUT_DIR}"
echo "[E2E] 원격 Supabase DB에는 아무 것도 쓰지 않습니다."

exec "${VENV_PYTHON}" -m tests.e2e.run_harness --out "${OUT_DIR}" "$@"
