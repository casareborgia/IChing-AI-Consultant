"""파서가 각 권 끝의 부록을 마지막 괘로 빨아들이지 않는지 확인한다.

실제로 났던 사고를 최소 형태로 재현한 것이다.
  - 하경 끝(괘64): 계사전·설괘전·서괘전·잡괘전이 6효 소상전과 1효 효사로 흘러들어
                   효사가 9,688자가 됐다. 계사전이 효사를 인용하며 '初六은'으로
                   시작하는 바람에 파서가 그것을 효사로 오인한 것이 결정적이었다.
  - 상경 끝(괘30): 하도낙서 도판 HTML이 6효 소상전에 붙어 10,649자가 됐다.

부록 차단을 지우면 이 테스트들은 실패한다.
"""
import os
import sys

sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), "..", "scripts")))

from parse_jeonguiu import parse_text, validate  # noqa: E402


def _one(text):
    result = parse_text(text)
    assert len(result) == 1
    return result[0]


def test_하경_끝_계사전이_괘64로_들어오지_않는다():
    h = _one(
        "64\\. 未濟 ䷿\n\n"
        "上九는 有孚于飮酒ㅣ면 无咎어니와\n\n"
        "象曰 飮酒濡首ㅣ 亦不知節也ㅣ라\n\n"
        "繫辭上傳 天尊地卑니 乾坤ㅣ 定矣오\n\n"
        "初六은 藉用白茅ㅣ니 无咎ㅣ라니 子曰 苟錯諸地라도 而可矣어늘\n\n"
        "夬 決也ㅣ라 剛決柔也\n"
    )
    by_pos = {l["position"]: l for l in h["lines"]}

    assert by_pos[6]["sosang"] == "象曰 飮酒濡首ㅣ 亦不知節也ㅣ라"
    assert "繫辭" not in by_pos[6]["sosang"]
    # 계사전이 인용한 '初六은 藉用白茅'가 1효 효사로 둔갑하면 안 된다
    assert 1 not in by_pos
    assert not any("白茅" in l["original"] for l in h["lines"])


def test_상경_끝_하도낙서_도판이_괘30으로_들어오지_않는다():
    h = _one(
        "30\\. 離 ䷝\n\n"
        "上九는 王用出征이면 有嘉ㅣ니\n\n"
        "象曰 王用出征은 以正邦也ㅣ라\n\n"
        "\\<span class='zebra_tips' \\>河\\</span\\>\\<span class='zebra_tips' \\>圖\\</span\\>\n\n"
        "○ 劉氏曰 伏羲氏繼天而王하여 受河圖而畫之하시니\n"
    )
    sosang = h["lines"][-1]["sosang"]

    assert sosang == "象曰 王用出征은 以正邦也ㅣ라"
    assert "span" not in sosang
    assert h["notes"] == []      # 도판 해설(○)까지 함께 끊긴다


def test_주석이_부록을_인용해도_끊기지_않는다():
    """정전 주석은 본문 안에서 '繫辭曰', '序卦에'로 부록을 수시로 인용한다.

    포함 검사로 부록을 판정하면 멀쩡한 괘가 여기서 잘린다. 그래서 표제는
    블록 첫머리에서만 인정한다.
    """
    h = _one(
        "32\\. 恒 ䷟\n\n"
        "恒은 亨야 无咎니\n\n"
        "\\[傳\\] 恒은 序卦에 夫婦之道는 不可以不久也라 繫辭曰 天下何思何慮리오\n\n"
        "初六은 浚恒이라\n\n"
        "象曰 浚恒之凶은 始애 求深也ㅣ라\n"
    )
    assert h["guasa"]["original"] == "恒은 亨야 无咎니"
    assert len(h["guasa"]["commentary"]) == 1
    assert "繫辭曰" in h["guasa"]["commentary"][0]
    assert len(h["lines"]) == 1


def test_validate가_오염된_효사를_잡아낸다():
    """가드가 실패할 줄 아는지 본다. 오염을 넣으면 경고가 나와야 한다."""
    clean = _one(
        "3\\. 屯 ䷂\n\n"
        "屯은 元亨코 利貞니\n\n"
        "彖曰 屯은 剛柔ㅣ 始交而難生니\n\n"
        "初九는 磐桓이니\n\n"
        "象曰 雖磐桓나 志行正也ㅣ라\n"
    )
    line = clean["lines"][0]

    assert not [w for w in validate([clean]) if "[길이]" in w or "[마크업]" in w]

    line["original"] += " 繫辭上傳 天尊地卑니 乾坤ㅣ 定矣오" * 20
    assert [w for w in validate([clean]) if "[길이]" in w]

    line["sosang"] += "<span class='zebra_tips'>河</span>"
    assert [w for w in validate([clean]) if "[마크업]" in w]
