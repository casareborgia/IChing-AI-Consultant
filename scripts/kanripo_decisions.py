#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
이관 손검토 판정표.

`review_kanripo_diff.py`가 뽑은 대조표를 검토해 확정한 것만 모았다.
적용은 `apply_decisions.py`가 한다. 판정을 바꾸려면 여기만 고치면 된다.

--------------------------------------------------------------------------
판정 기준은 **통행본이 아니라 정전(伊川易傳) 저본**이다.

정이천은 저본을 고쳐 읽고 그 위에서 해석을 전개한 자리가 여럿이라,
통행본으로 판정하면 주석과 어긋난다. 실제로 그렇게 틀린 자리가 셋 있었다:

    15 謙  주석에 `濟當爲際` — 濟를 際로 고쳐 읽으라 명시. 통행본은 濟
    27 頤  주석이 `耽耽然如虎視` — 저본이 耽耽. 통행본은 眈眈
    43 夬  호공의 재배열을 물리치고 `當云…`으로 자기 안을 냄

그래서 근거는 전부 **정전 주석이 그 표기를 실제로 쓰는가**로 잡았다.
`source` 필드가 그 인용문이다. 근거가 없으면 확정하지 않고 OPEN에 둔다.
--------------------------------------------------------------------------

slot 표기
    ("guasa"|"danjeon"|"daesang"|"munon", "original")
    ("line", 효번호, "original"|"sosang")
    ("commentary",)   해당 괘의 주석 전체에서 찾는다
"""

# ── 확정: 원문을 정전 저본 표기로 되돌린다 ──────────────────────────────
DECISIONS = [
    # --- 정전 주석이 표기를 직접 인용하는 자리 ---
    dict(hexagram=15, slot=("danjeon", "original"),
         find="天道下濟而光明", replace="天道下際而光明",
         source="濟當爲際 … 天之道以其氣下際故能化育萬物 … 下際謂下交也",
         note="정이천이 濟를 際로 개독(改讀)한다고 명시했다"),
    dict(hexagram=27, slot=("line", 4, "original"),
         find="虎視眈眈", replace="虎視耽耽",
         source="耽耽然如虎視則能重其體貌", note="통행본은 眈眈이나 정전 저본은 耽耽"),
    dict(hexagram=27, slot=("line", 1, "original"),
         find="觀我朵頤", replace="觀我朶頤",
         source="乃觀我而朶頤 … 初之所以朶頤者四也"),
    dict(hexagram=27, slot=("line", 1, "sosang"),
         find="觀我朵頤", replace="觀我朶頤", source="初之所以朶頤者四也"),
    dict(hexagram=35, slot=("line", 2, "original"),
         find="受茲介福", replace="受玆介福", source="受玆介福以中正之道也"),
    dict(hexagram=35, slot=("line", 2, "sosang"),
         find="受茲介福", replace="受玆介福", source="受玆介福以中正之道也"),
    dict(hexagram=47, slot=("line", 3, "original"),
         find="據于蒺蔾", replace="據于蒺藜", source="其不安猶藉刺據于蒺藜也"),
    dict(hexagram=47, slot=("line", 3, "sosang"),
         find="據于蒺蔾", replace="據于蒺藜", source="其不安猶藉刺據于蒺藜也"),
    dict(hexagram=55, slot=("line", 6, "original"),
         find="闃其無人", replace="閴其無人", source="故闚其戶閴其無人也"),
    dict(hexagram=55, slot=("line", 6, "sosang"),
         find="闃其無人", replace="閴其無人", source="故闚其戶閴其無人也"),
    dict(hexagram=26, slot=("danjeon", "original"),
         find="煇光日新", replace="輝光日新", source="所畜能大充實而有輝光"),
    dict(hexagram=29, slot=("line", 5, "original"),
         find="衹旣平", replace="祗旣平", source="必祗旣平乃得無咎"),
    dict(hexagram=40, slot=("danjeon", "original"),
         find="百果草木皆甲坼", replace="百果草木皆甲拆",
         source="雷雨作而萬物皆生發甲拆"),
    dict(hexagram=49, slot=("daesang", "original"),
         find="君子以治厤明時", replace="君子以治歷明時",
         source="以治歷數明四時之序也"),
    dict(hexagram=64, slot=("line", 2, "sosang"),
         find="中以行直也", replace="中以行正也",
         source="以曳輪而得中道乃正也"),
    dict(hexagram=4, slot=("guasa", "original"),
         find="童蒙來求我", replace="童蒙求我", source="匪我求童蒙童蒙求我"),
    dict(hexagram=4, slot=("danjeon", "original"),
         find="童蒙來求我", replace="童蒙求我", source="匪我求童蒙童蒙求我志應也"),
    dict(hexagram=17, slot=("danjeon", "original"),
         find="而天下隨之，隨之時義大矣哉", replace="而天下隨時，隨時之義大矣哉",
         source="天下所隨者時也故云天下隨時 … 君子之道隨時而動"),

    # --- 정전 주석이 그 구절을 아예 인용하지 않는 자리 (저본에 없다) ---
    dict(hexagram=22, slot=("danjeon", "original"),
         find="。剛柔交錯、天文也。", replace="。天文也。",
         source="(주석) 此承上文言陰陽剛柔相文者天之文也",
         note="정전은 剛柔交錯 넉 자를 인용하지 않고 陰陽剛柔相文者로 푼다. "
              "왕필본 계열에는 없는 구절이다"),
    dict(hexagram=5, slot=("line", 6, "sosang"),
         find="敬之終吉」也，雖不當位", replace="敬之終吉」，雖不當位",
         source="然能敬愼以自處則陽不能陵終得其吉雖不當位而未至於大失也"),

    # --- 정이천이 연문(羨文)으로 배제한 자리 ---
    dict(hexagram=45, slot=("guasa", "original"),
         find="萃 亨，王假有廟。", replace="萃 王假有廟。",
         source="萃下有亨字羡文也 亨字自在下與渙不同",
         note="정이천이 괘사 머리의 亨을 연문으로 명시했다. 뒤의 亨은 남긴다"),

    # --- 사고전서본 판각 오자 (주석) ---
    dict(hexagram=1, slot=("commentary",),
         find="大哉乾無贊", replace="大哉乾元贊",
         source="贊乾元始萬物之道大也",
         note="「大哉乾元」을 풀이하는 문장이라 표제어가 元이어야 한다"),
    dict(hexagram=7, slot=("commentary",),
         find="以夫子禮樂", replace="以天子禮樂",
         source="周公能爲人臣不能爲之功則可用人臣不得用之禮樂",
         note="'신하가 쓸 수 없는 예악' = 天子의 예악"),
    dict(hexagram=7, slot=("commentary",),
         find="豈唯無功必以致凶也", replace="豈唯無功所以致凶也",
         source="倚付二三安能成功豈唯無功所以致凶也"),
    # --- EQUIVALENT_PAIRS(己/已/巳, 包/苞, 他/它 …)로 접혀 대조표에 안 나오던 자리 ---
    # 판각에서 늘 헷갈리는 짝이라 "정규화하지 말고 대조에서만 접자"고 했는데,
    # 원문에서는 그 접기가 실제 이문을 통째로 가렸다. 革괘가 대표적이다 —
    # 已日(날이 지난 뒤)과 巳日(간지의 巳日)은 뜻이 아예 다르다.
    dict(hexagram=43, slot=("line", 3, "original"),
         find="壯于頄，有凶。君子夬夬，獨行遇雨、若濡，有慍無咎。",
         replace="壯于頄，有凶。獨行遇雨，君子夬夬、若濡，有慍無咎。",
         source="爻辭差錯 … 安定胡公移其文曰… 亦未安也 "
                "當云壯于頄有凶獨行遇雨君子夬夬若濡有慍無咎",
         note="정이천이 호공안을 물리치고 낸 자기 안(當云)이 구본 어순과 같다. "
              "앞서 신본 유지로 판정했던 것을 뒤집는다"),
    dict(hexagram=49, slot=("guasa", "original"),
         find="巳日乃孚", replace="已日乃孚",
         source="變其故則人未能遽信故必已日然後人心信從"),
    dict(hexagram=49, slot=("danjeon", "original"),
         find="「巳日乃孚」", replace="「已日乃孚」",
         source="必已日然後人心信從"),
    dict(hexagram=49, slot=("line", 2, "original"),
         find="巳日乃革之", replace="已日乃革之",
         source="又必待上下之信故已日乃革之也"),
    dict(hexagram=49, slot=("line", 2, "sosang"),
         find="「巳日革之」", replace="「已日革之」",
         source="故已日乃革之也"),
    dict(hexagram=8, slot=("line", 1, "original"),
         find="終來，有它吉", replace="終來，有他吉",
         source="則終能來有他吉也 他非此也外也"),
    dict(hexagram=8, slot=("line", 1, "sosang"),
         find="「有它吉」", replace="「有他吉」", source="則終能來有他吉也"),
    dict(hexagram=11, slot=("line", 2, "original"),
         find="苞荒", replace="包荒",
         source="包荒用馮河不遐遺朋亡四者處泰之道也"),
    dict(hexagram=11, slot=("line", 2, "sosang"),
         find="「苞荒、", replace="「包荒、", source="包荒用馮河不遐遺朋亡四者"),
    dict(hexagram=61, slot=("line", 1, "original"),
         find="有它不燕", replace="有他不燕",
         source="旣得所信則當誠一 若有他則不得其燕安矣"),
    dict(hexagram=14, slot=("line", 4, "sosang"),
         find="明辯晢也", replace="明辨晢也",
         source="蓋有明辨之智也 … 賢智之人明辨物理"),
    # --- 보류로 뒀던 12건. 정전 주석에서 근거를 찾아 확정한다 ---
    # 정이천이 저본을 고쳐 읽으라고 명시한 자리가 여기 둘 더 있다.
    dict(hexagram=63, slot=("line", 4, "original"),
         find="繻有衣袽", replace="濡有衣袽",
         source="繻當作濡謂滲漏也 舟有罅漏則塞以衣袽",
         note="15 謙의 `濟當爲際`와 같은 개독 명시"),
    dict(hexagram=53, slot=("line", 6, "original"),
         find="鴻漸于陸", replace="鴻漸于逵",
         source="安定胡公以陸爲逵 逵雲路也 … 爾雅九達謂之逵 … 如鴻之離所止而飛于雲空",
         note="정이천이 호공의 逵를 받아 '구름길'로 해석을 전개한다. 陸(뭍)으로는 "
              "飛于雲空이라는 풀이가 성립하지 않는다"),
    dict(hexagram=51, slot=("line", 5, "original"),
         find="意無喪有事", replace="億無喪有事",
         source="億度也 貝所有之資也", note="주석이 億을 '헤아리다'로 훈석한다"),
    dict(hexagram=26, slot=("line", 1, "original"),
         find="利己", replace="利已",
         source="初九處不得中故戒以有危宜已", note="주석의 宜已가 효사 利已를 받는다"),
    dict(hexagram=26, slot=("line", 1, "sosang"),
         find="「有厲利己」", replace="「有厲利已」", source="故戒以有危宜已"),
    dict(hexagram=47, slot=("line", 2, "original"),
         find="利用享祀", replace="利用亨祀",
         source="利用亨祀 亨祀以至誠通神明也 … 利用至誠如亨祀然",
         note="효사를 직접 받는 자리는 亨祀다. 뒤의 `二云享祀`는 五효와 견주는 "
              "느슨한 지칭이라 저본 근거가 되지 않는다"),
    dict(hexagram=4, slot=("line", 2, "original"),
         find="苞蒙", replace="包蒙",
         source="(주석 첫머리) 包含容也",
         note="주석이 효사의 包를 含容으로 훈석한다. 사고전서본은 효사만 苞로 "
              "새겨 주석과 어긋난다"),
    dict(hexagram=4, slot=("commentary",),
         find="包舍容也", replace="包含容也",
         source="包，含容也 — 包를 훈석하는 문장. `包舍容也`는 뜻이 되지 않는다"),
    dict(hexagram=12, slot=("line", 2, "original"),
         find="苞承", replace="包承", source="志所包畜者在承順乎上"),
    dict(hexagram=12, slot=("line", 3, "original"),
         find="苞羞", replace="包羞", source="其所包畜謀慮邪濫無所不至可羞恥也"),
    dict(hexagram=12, slot=("line", 3, "sosang"),
         find="「苞羞」", replace="「包羞」", source="其所包畜 … 可羞恥也"),
    dict(hexagram=21, slot=("daesang", "original"),
         find="明罰勑法", replace="明罰勅法",
         source="法其明與威以明其刑罰飭其法令",
         note="주석이 그 글자를 飭(정돈하다)으로 푼다. 勅/勑은 자형 변형이라 "
              "통용 표준인 勅으로 맞춘다"),
    # 辨/辯 — 易 문맥에서는 모두 '분별'이다. 14 大有 明辨晢也를 이미 辨으로
    # 확정했고, 정전 주석도 1 乾에서 學聚問辨, 10 履에서 分辨上下를 쓴다.
    # 사고전서본은 자리마다 辨과 辯을 섞어 써서 같은 낱말이 두 글자가 된다.
    dict(hexagram=1, slot=("munon", "original"),
         find="問以辯之", replace="問以辨之", source="學聚問辨進德也"),
    dict(hexagram=2, slot=("munon", "original"),
         find="由辯之不早辯也", replace="由辨之不早辨也",
         source="小積成大辯之於早 — 신본은 원문 辯/辨을 섞어 쓴다"),
    dict(hexagram=10, slot=("daesang", "original"),
         find="君子以辯上下", replace="君子以辨上下",
         source="(구본 주석) 君子觀履之象而分辨上下使各當其分"),
]

# ── 신본 그대로 두기로 한 것 (기록용, 적용할 변경 없음) ────────────────
KEPT = [
    (1, "단전 大明終始", "주석 `大明天道之終始`"),
    (8, "단전 比吉也", "주석 `比吉也比者吉之道也`"),
    (48, "단전 往來井井", "주석 `往來井井其用也周常也`"),
    (62, "단전 亨", "주석 `事有時而當然有待過而後能亨者故小過自有亨義` — "
                    "정이천이 小過에 亨의 뜻이 있다고 명시한다"),
    (50, "주석 終爲成功", "`井鼎皆以終爲成功…井之功用皆在上出`. 구본처럼 앞도 "
                        "上出이면 井의 차별점이 사라져 문답이 무너진다"),
]

# ── 보류: 근거가 없어 확정하지 않는다 ──────────────────────────────────
OPEN: list = []   # 12건 전부 정전 주석에서 근거를 찾아 확정했다
