# 원전 출처 (Provenance)

배포물에 들어가는 텍스트가 어디서 왔고 왜 써도 되는지 남긴다.
CLAUDE.md 「법적 확인 사항」의 첫 항목에 대한 근거 문서다.

## 현재 사용 중

| 자료 | 출처 | 리포 | 취득일 | 판본 |
|---|---|---|---|---|
| 주역 경문 | Kanseki Repository | `KR1a0001` | 2026-08-15 | tls본, 표점 있음 |
| 정전(程傳) | Kanseki Repository | `KR1a0016` | 2026-08-15 | 문연각 사고전서본(WYG), 표점 없음 |

- 수집: `python scripts/fetch_kanripo.py` → `data/kanripo/`
- 파싱: `python scripts/parse_kanripo.py` → `data/hexagrams_kanripo.json`
- 판정 반영: `python scripts/apply_decisions.py`
- 검증: `python scripts/verify_kanripo.py`
- RAG 청크: `python scripts/build_rag_chunks.py -i data/hexagrams_kanripo.json -o data/rag_chunks_kanripo.json`
- 대조표 재생성: `python scripts/review_kanripo_diff.py -o data/kanripo_review.md`

### 저본 판정

산출물은 원본 그대로가 아니다. 손검토로 확정한 24곳을 `apply_decisions.py`가
고쳐 얹는다. 판정표와 근거는 `scripts/kanripo_decisions.py`에 있다.

기준은 **통행본이 아니라 정전 저본**이다. 정이천이 저본을 고쳐 읽고 그 위에서
해석을 전개한 자리가 있어서, 통행본으로 맞추면 주석과 어긋난다
(15 謙 `濟當爲際`, 27 頤 `耽耽然如虎視`, 45 萃 `萃下有亨字羡文也`).

보류 5건은 고치지 않고 해당 괘의 `open_questions`에 표시만 남겼다 —
53 漸(逵/陸) · 51 震(億/意) · 63 旣濟(濡/繻) · 21 噬嗑(勅/勑) · 62 小過(亨 유무).

### 저작권 판단

**저본은 보호기간 만료.** 경문은 고대 문헌이고, 정전은 정이(程頤, 1033–1107)
저작이다. 중문 위키문헌도 같은 사고전서본 『伊川易傳』을 "此作品在全世界都屬於
公有領域"(전 세계 공유 영역)으로 명시한다.

**Kanripo 기여분은 CC BY-SA 4.0.** 전사와 마크업이 그 대상인데, 파서는 그
마크업(`<pb:>` 페이지 태그, `¶` 행 표시, 전각 들여쓰기)을 전부 버리고 구조를
다시 세운다. 그래도 출처는 표시한다 — 앱 고지에 다음을 넣는다:

> 주역 원문 및 정전 주석 텍스트: Kanseki Repository (漢籍リポジトリ),
> 교토대학 인문과학연구소. CC BY-SA 4.0.

## 쓰지 않기로 한 것

| 자료 | 이유 |
|---|---|
| 동양고전종합DB (전통문화연구회) | 이용약관이 영리 목적 사용 금지 |
| 한국고전종합DB (한국고전번역원) | 공공누리 제4유형 — 상업적 이용 금지 + 변경 금지 |
| ctext.org | 사이트 데이터가 CC BY-**NC**-SA 3.0 |
| 현대 한국어 번역서 | 2차적저작물, 보호기간 내 |

`data/source/`의 현토본(주역전의 상·하)은 현토·교감 표기가 현대 편집자의
작업물이고 출처 약관이 영리 사용을 막는다. gitignore 상태이며 배포물에
넣지 않는다. 이관이 끝나면 지운다.

## 한글 번역

괘사·효사 450건은 자체 생성했다(`scripts/translate.py`). 저작권 있는 번역서를
저본으로 쓰지 않았다. 다만 초판 번역은 위 현토본을 저본으로 삼았으므로,
현토(=구두 해석)가 번역에 반영됐을 여지가 있다. 이관 후 Kanripo 경문을
저본으로 재실행해 그 고리를 끊는다.

## 미확보

- 주자 『본의(本義)』 — `KR1a0031`(原本周易本義) / `KR1a0032`(別本)로 확보 가능.
  `fetch_kanripo.py --with-benui`로 받는다. 割註가 `(…/…)` 인라인 괄호라
  전용 파서가 필요하다.
