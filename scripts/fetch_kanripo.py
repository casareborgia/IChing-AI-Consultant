#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kanripo(漢籍リポジトリ)에서 주역 원전을 내려받는다.

받는 것:
    KR1a0001  周易 (경문)        — 64파일 = 64괘 1:1, tls본, 표점 있음
    KR1a0016  伊川易傳 (정전)     — 4권, 문연각 사고전서본, 표점 없음
    KR1a0031  原本周易本義 (본의)  — 15파일, 선택 (--with-benui)

저작권: 저본인 정이(1107졸)·주희(1200졸) 저작은 보호기간 만료. Kanripo의
전사·마크업 기여분은 CC BY-SA 4.0이며, 이 파서는 그 마크업(<pb:> 태그, ¶)을
전부 버리고 구조를 다시 세운다. 출처는 data/PROVENANCE.md에 남긴다.

사용법:
    python scripts/fetch_kanripo.py                 # 경문 + 정전
    python scripts/fetch_kanripo.py --with-benui    # 본의까지
"""

import argparse
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

RAW = "https://raw.githubusercontent.com/kanripo/{repo}/master/{name}"

# (리포지토리, 파일명 목록) — Kanripo는 리포마다 파일 분할 방식이 다르다.
WORKS = {
    "gyeongmun": ("KR1a0001", [f"KR1a0001_{i:03d}.txt" for i in range(1, 70)]),
    "jeongjeon": ("KR1a0016", [f"KR1a0016_{i:03d}.txt" for i in range(0, 5)]),
    "benui":     ("KR1a0031", [f"KR1a0031_{i:03d}.txt" for i in range(0, 15)]),
}

DEFAULT_OUT = Path(__file__).resolve().parent.parent / "data" / "kanripo"


def fetch_one(repo: str, name: str, out_dir: Path, retries: int = 3) -> tuple[str, int]:
    """파일 하나를 받는다. 실패하면 지수 백오프로 재시도한다."""
    dest = out_dir / name
    url = RAW.format(repo=repo, name=name)
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                body = resp.read()
            dest.write_bytes(body)
            return name, len(body)
        except urllib.error.HTTPError as e:
            if e.code == 404:            # 파일 수가 리포마다 달라 404는 정상 종료 조건
                return name, 0
            if attempt == retries - 1:
                raise
        except urllib.error.URLError:
            if attempt == retries - 1:
                raise
        time.sleep(2 ** attempt)
    return name, 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Kanripo 주역 원전 수집")
    ap.add_argument("-o", "--out", type=Path, default=DEFAULT_OUT,
                    help=f"저장 위치 (기본: {DEFAULT_OUT})")
    ap.add_argument("--with-benui", action="store_true",
                    help="주자 『본의』(KR1a0031)까지 받는다")
    args = ap.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    targets = ["gyeongmun", "jeongjeon"] + (["benui"] if args.with_benui else [])

    total_bytes = total_files = 0
    for key in targets:
        repo, names = WORKS[key]
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda n: fetch_one(repo, n, args.out), names))
        got = [(n, s) for n, s in results if s > 0]
        total_files += len(got)
        total_bytes += sum(s for _, s in got)
        print(f"  {key:<10} {repo}  {len(got):>2}파일  {sum(s for _, s in got):>8,}B")

    print(f"\n{total_files}파일 {total_bytes:,}B → {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
