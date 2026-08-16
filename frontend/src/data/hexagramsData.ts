import { CastResult, HexagramMeta, LineInfo, LineValue } from '../types/iching';

export const HEXAGRAM_BINARY_TO_ID: Record<string, number> = {
  "111111": 1,   // 乾 (중천건)
  "000000": 2,   // 坤 (중지곤)
  "100010": 3,   // 屯 (수뢰준)
  "010001": 4,   // 蒙 (산수몽)
  "111010": 5,   // 需 (수천수)
  "010111": 6,   // 訟 (천수송)
  "010000": 7,   // 師 (지수사)
  "000010": 8,   // 比 (수지비)
  "111011": 9,   // 小畜 (풍천소축)
  "110111": 10,  // 履 (천택리)
  "111000": 11,  // 泰 (지천태)
  "000111": 12,  // 否 (천지비)
  "101111": 13,  // 同人 (천화동인)
  "111101": 14,  // 大有 (화천대유)
  "001000": 15,  // 謙 (지산겸)
  "000100": 16,  // 豫 (뇌지예)
  "100110": 17,  // 隨 (택뢰수)
  "011001": 18,  // 蠱 (산풍고)
  "110000": 19,  // 臨 (지택임)
  "000011": 20,  // 觀 (풍지관)
  "100101": 21,  // 噬嗑 (화뢰서합)
  "101001": 22,  // 賁 (산화비)
  "000001": 23,  // 剝 (산지박)
  "100000": 24,  // 復 (지뢰복)
  "100111": 25,  // 无妄 (천뢰무망)
  "111001": 26,  // 大畜 (산천대축)
  "100001": 27,  // 頤 (산뢰이)
  "011110": 28,  // 大過 (택풍대과)
  "010010": 29,  // 坎 (중수감)
  "101101": 30,  // 離 (중화리)
  "001110": 31,  // 咸 (택산함)
  "011100": 32,  // 恒 (뇌풍항)
  "001111": 33,  // 遯 (천산둔)
  "111100": 34,  // 大壯 (뇌천대장)
  "000101": 35,  // 晉 (화지진)
  "101000": 36,  // 明夷 (지화명이)
  "101011": 37,  // 家人 (풍화가인)
  "110101": 38,  // 睽 (화택규)
  "001010": 39,  // 蹇 (수산건)
  "010100": 40,  // 解 (뇌수해)
  "110001": 41,  // 損 (산택손)
  "100011": 42,  // 益 (풍뢰익)
  "111110": 43,  // 夬 (택천쾌)
  "011111": 44,  // 姤 (천풍구)
  "000110": 45,  // 萃 (택지췌)
  "011000": 46,  // 升 (지풍승)
  "010110": 47,  // 困 (택수곤)
  "011010": 48,  // 井 (수풍정)
  "101110": 49,  // 革 (택화혁)
  "011101": 50,  // 鼎 (화풍정)
  "100100": 51,  // 震 (중뇌진)
  "001001": 52,  // 艮 (중산간)
  "001011": 53,  // 漸 (풍산점)
  "110100": 54,  // 歸妹 (뇌택귀매)
  "101100": 55,  // 豐 (뇌화풍)
  "001101": 56,  // 旅 (화산여)
  "011011": 57,  // 巽 (중풍손)
  "110110": 58,  // 兌 (중택태)
  "010011": 59,  // 渙 (풍수환)
  "110010": 60,  // 節 (수택절)
  "110011": 61,  // 中孚 (풍택중부)
  "001100": 62,  // 小過 (뇌산소과)
  "101010": 63,  // 旣濟 (수화기제)
  "010101": 64,  // 未濟 (화수미제)
};

export const HEXAGRAM_ID_TO_BINARY: Record<number, string> = Object.fromEntries(
  Object.entries(HEXAGRAM_BINARY_TO_ID).map(([k, v]) => [v, k])
);

export const HEXAGRAMS_META: Record<number, HexagramMeta> = {
  1: { id: 1, nameHanja: '乾', nameHangul: '건', fullNameHangul: '중천건', unicodeSymbol: '䷀', upperTrigram: '天 (하늘)', lowerTrigram: '天 (하늘)', natureSummary: '위아래가 모두 하늘로 가득 찬 상', coreTheme: '창조적 역동성, 쉼 없는 정진, 바른 도리', binary: '111111' },
  2: { id: 2, nameHanja: '坤', nameHangul: '곤', fullNameHangul: '중지곤', unicodeSymbol: '䷁', upperTrigram: '地 (땅)', lowerTrigram: '地 (땅)', natureSummary: '넓고 깊은 대지가 만물을 품는 상', coreTheme: '수용, 온화한 순응, 너른 포용력', binary: '000000' },
  3: { id: 3, nameHanja: '屯', nameHangul: '준', fullNameHangul: '수뢰준', unicodeSymbol: '䷂', upperTrigram: '水 (구름/물)', lowerTrigram: '雷 (우레)', natureSummary: '구름 아래 우레가 움직이며 싹이 트는 상', coreTheme: '창업의 어려움, 끈기, 첫걸음의 신중함', binary: '100010' },
  4: { id: 4, nameHanja: '蒙', nameHangul: '몽', fullNameHangul: '산수몽', unicodeSymbol: '䷃', upperTrigram: '山 (산)', lowerTrigram: '水 (험난한 물)', natureSummary: '산 아래 험한 샘물이 솟아나는 상', coreTheme: '배움의 시작, 분별력 기르기, 겸허한 가르침', binary: '010001' },
  5: { id: 5, nameHanja: '需', nameHangul: '수', fullNameHangul: '수천수', unicodeSymbol: '䷄', upperTrigram: '水 (비구름)', lowerTrigram: '天 (하늘)', natureSummary: '하늘 위에 비구름이 모여 비를 기다리는 상', coreTheme: '신뢰 속의 기다림, 내실 다지기, 조급함 경계', binary: '111010' },
  6: { id: 6, nameHanja: '訟', nameHangul: '송', fullNameHangul: '천수송', unicodeSymbol: '䷅', upperTrigram: '天 (하늘)', lowerTrigram: '水 (물)', natureSummary: '하늘은 위로 오르고 물은 아래로 흘러 뜻이 갈리는 상', coreTheme: '갈등과 다툼, 멈추어 타협하기, 객관적 조율', binary: '010111' },
  7: { id: 7, nameHanja: '師', nameHangul: '사', fullNameHangul: '지수사', unicodeSymbol: '䷆', upperTrigram: '地 (땅)', lowerTrigram: '水 (물)', natureSummary: '땅속에 물이 모여 군중을 이루는 상', coreTheme: '조직과 규율, 올바른 지도력, 목적의 정당성', binary: '010000' },
  8: { id: 8, nameHanja: '比', nameHangul: '비', fullNameHangul: '수지비', unicodeSymbol: '䷇', upperTrigram: '水 (물)', lowerTrigram: '地 (땅)', natureSummary: '물이 땅 위를 적시며 조화를 이루는 상', coreTheme: '친밀한 연대, 진실한 화합, 서로 돕는 관계', binary: '000010' },
  9: { id: 9, nameHanja: '小畜', nameHangul: '소축', fullNameHangul: '풍천소축', unicodeSymbol: '䷈', upperTrigram: '風 (바람)', lowerTrigram: '天 (하늘)', natureSummary: '하늘 위로 바람이 불어 구름을 모으는 상', coreTheme: '작은 축적, 유연한 소통, 점진적 준비', binary: '111011' },
  10: { id: 10, nameHanja: '履', nameHangul: '리', fullNameHangul: '천택리', unicodeSymbol: '䷉', upperTrigram: '天 (하늘)', lowerTrigram: '澤 (연못)', natureSummary: '하늘 아래 연못이 자리하여 분수를 지키는 상', coreTheme: '예절과 조심성, 위험 속의 침착함, 바른 태도', binary: '110111' },
  11: { id: 11, nameHanja: '泰', nameHangul: '태', fullNameHangul: '지천태', unicodeSymbol: '䷊', upperTrigram: '地 (땅)', lowerTrigram: '天 (하늘)', natureSummary: '땅의 기운은 내리고 하늘의 기운은 올라 서로 사귀는 상', coreTheme: '태평과 번영, 원활한 소통, 작은 것이 가고 큰 것이 옴', binary: '111000' },
  12: { id: 12, nameHanja: '否', nameHangul: '비', fullNameHangul: '천지비', unicodeSymbol: '䷋', upperTrigram: '天 (하늘)', lowerTrigram: '地 (땅)', natureSummary: '하늘은 위에 머물고 땅은 아래에 머물러 막히는 상', coreTheme: '폐쇄와 침체, 도를 지키며 은인자중, 내면의 절개', binary: '000111' },
  13: { id: 13, nameHanja: '同人', nameHangul: '동인', fullNameHangul: '천화동인', unicodeSymbol: '䷌', upperTrigram: '天 (하늘)', lowerTrigram: '火 (불)', natureSummary: '하늘과 불이 같은 밝음을 지향하는 상', coreTheme: '열린 연대, 공정한 동행, 사사로움 극복', binary: '101111' },
  14: { id: 14, nameHanja: '大有', nameHangul: '대유', fullNameHangul: '화천대유', unicodeSymbol: '䷍', upperTrigram: '火 (태양/불)', lowerTrigram: '天 (하늘)', natureSummary: '하늘 높이 태양이 떠올라 온 세상을 비추는 상', coreTheme: '풍요와 성취, 관용과 나눔, 겸손한 관리', binary: '111101' },
  15: { id: 15, nameHanja: '謙', nameHangul: '겸', fullNameHangul: '지산겸', unicodeSymbol: '䷎', upperTrigram: '地 (땅)', lowerTrigram: '山 (산)', natureSummary: '높은 산이 땅 아래로 자신을 낮추고 있는 상', coreTheme: '진정한 겸손, 균형 맞추기, 비움으로써 채워짐', binary: '001000' },
  16: { id: 16, nameHanja: '豫', nameHangul: '예', fullNameHangul: '뇌지예', unicodeSymbol: '䷏', upperTrigram: '雷 (우레)', lowerTrigram: '地 (땅)', natureSummary: '땅속에서 우레가 터져 나와 봄의 활기를 여는 상', coreTheme: '기쁨과 대비, 조화로운 열정, 나태함 경계', binary: '000100' },
  17: { id: 17, nameHanja: '隨', nameHangul: '수', fullNameHangul: '택뢰수', unicodeSymbol: '䷐', upperTrigram: '澤 (연못)', lowerTrigram: '雷 (우레)', natureSummary: '연못 속에 우레가 잠겨 때에 순응하는 상', coreTheme: '시류에 따름, 유연한 적응, 바른 가치를 좇음', binary: '100110' },
  18: { id: 18, nameHanja: '蠱', nameHangul: '고', fullNameHangul: '산풍고', unicodeSymbol: '䷑', upperTrigram: '山 (산)', lowerTrigram: '風 (바람)', natureSummary: '산 아래 바람이 정체되어 썩어가는 상', coreTheme: '폐단 혁신, 묵은 문제의 쇄신, 새로운 시작', binary: '011001' },
  19: { id: 19, nameHanja: '臨', nameHangul: '임', fullNameHangul: '지택임', unicodeSymbol: '䷒', upperTrigram: '地 (땅)', lowerTrigram: '澤 (연못)', natureSummary: '땅이 연못을 굽어살피며 감싸는 상', coreTheme: '다가섬과 지도, 기운의 상승, 멀리 내다보는 안목', binary: '110000' },
  20: { id: 20, nameHanja: '觀', nameHangul: '관', fullNameHangul: '풍지관', unicodeSymbol: '䷓', upperTrigram: '風 (바람)', lowerTrigram: '地 (땅)', natureSummary: '바람이 땅 위를 두루 지나며 관찰하는 상', coreTheme: '통찰과 성찰, 깊은 관조, 본보기가 됨', binary: '000011' },
  21: { id: 21, nameHanja: '噬嗑', nameHangul: '서합', fullNameHangul: '화뢰서합', unicodeSymbol: '䷔', upperTrigram: '火 (번개)', lowerTrigram: '雷 (우레)', natureSummary: '우레와 번개가 함께 쳐서 장애물을 부수는 상', coreTheme: '장애물 타파, 결단과 집행, 명확한 시비 분별', binary: '100101' },
  22: { id: 22, nameHanja: '賁', nameHangul: '비', fullNameHangul: '산화비', unicodeSymbol: '䷕', upperTrigram: '山 (산)', lowerTrigram: '火 (불)', natureSummary: '산 아래 불이 빛나며 자연을 수놓는 상', coreTheme: '품격과 꾸밈, 본질과 형식의 조화, 지나친 겉치레 경계', binary: '101001' },
  23: { id: 23, nameHanja: '剝', nameHangul: '박', fullNameHangul: '산지박', unicodeSymbol: '䷖', upperTrigram: '山 (산)', lowerTrigram: '地 (땅)', natureSummary: '산이 땅 위에 깎여 붕괴되는 상', coreTheme: '마모와 침식, 섣부른 행동 자제, 씨앗을 보존함', binary: '000001' },
  24: { id: 24, nameHanja: '復', nameHangul: '복', fullNameHangul: '지뢰복', unicodeSymbol: '䷗', upperTrigram: '地 (땅)', lowerTrigram: '雷 (우레)', natureSummary: '땅 깊은 곳에서 하나의 양기가 다시 꿈틀거리는 상', coreTheme: '회복과 귀환, 긍정의 싹, 순리를 되찾음', binary: '100000' },
  25: { id: 25, nameHanja: '无妄', nameHangul: '무망', fullNameHangul: '천뢰무망', unicodeSymbol: '䷘', upperTrigram: '天 (하늘)', lowerTrigram: '雷 (우레)', natureSummary: '하늘 아래 우레가 움직여 거짓 없이 순수한 상', coreTheme: '무위자연, 순수한 진정성, 억지 욕심 배제', binary: '100111' },
  26: { id: 26, nameHanja: '大畜', nameHangul: '대축', fullNameHangul: '산천대축', unicodeSymbol: '䷙', upperTrigram: '山 (산)', lowerTrigram: '天 (하늘)', natureSummary: '거대한 산이 하늘의 에너지를 품고 있는 상', coreTheme: '큰 축적, 역량과 지혜의 함양, 견고한 정진', binary: '111001' },
  27: { id: 27, nameHanja: '頤', nameHangul: '이', fullNameHangul: '산뢰이', unicodeSymbol: '䷚', upperTrigram: '山 (산)', lowerTrigram: '雷 (우레)', natureSummary: '산 아래 우레가 머물며 턱(입) 모양을 이루는 상', coreTheme: '양생과 언행 관리, 내면의 영양 공급, 절제', binary: '100001' },
  28: { id: 28, nameHanja: '大過', nameHangul: '대과', fullNameHangul: '택풍대과', unicodeSymbol: '䷛', upperTrigram: '澤 (연못)', lowerTrigram: '風 (나무/바람)', natureSummary: '연못이 나무 위로 넘쳐 대들보가 휘어지는 상', coreTheme: '과중한 부담, 비상시의 결단력, 기둥을 바로세움', binary: '011110' },
  29: { id: 29, nameHanja: '坎', nameHangul: '감', fullNameHangul: '중수감', unicodeSymbol: '䷜', upperTrigram: '水 (물)', lowerTrigram: '水 (물)', natureSummary: '물 위에 다시 깊은 물이 겹쳐 험난한 상', coreTheme: '거듭된 험난, 마음의 중심 지키기, 물처럼 유연히 통과', binary: '010010' },
  30: { id: 30, nameHanja: '離', nameHangul: '리', fullNameHangul: '중화리', unicodeSymbol: '䷝', upperTrigram: '火 (불)', lowerTrigram: '火 (불)', natureSummary: '두 개의 불길이 이어지며 찬란하게 타오르는 상', coreTheme: '밝은 지혜, 올바른 것에 의지함, 지속적인 열정', binary: '101101' },
  31: { id: 31, nameHanja: '咸', nameHangul: '함', fullNameHangul: '택산함', unicodeSymbol: '䷞', upperTrigram: '澤 (연못)', lowerTrigram: '山 (산)', natureSummary: '산 위에 연못이 있어 기운이 서로 감응하는 상', coreTheme: '진실한 공감, 무심한 이끌림, 마음과 마음의 소통', binary: '001110' },
  32: { id: 32, nameHanja: '恒', nameHangul: '항', fullNameHangul: '뇌풍항', unicodeSymbol: '䷟', upperTrigram: '雷 (우레)', lowerTrigram: '風 (바람)', natureSummary: '우레와 바람이 서로 어우러져 끊이지 않는 상', coreTheme: '한결같은 지속성, 초심 유지, 변함없는 신의', binary: '011100' },
  33: { id: 33, nameHanja: '遯', nameHangul: '둔', fullNameHangul: '천산둔', unicodeSymbol: '䷠', upperTrigram: '天 (하늘)', lowerTrigram: '山 (산)', natureSummary: '하늘 아래 산이 멀어지며 물러나는 상', coreTheme: '지혜로운 후퇴, 거리 두기, 소모적인 싸움 회피', binary: '001111' },
  34: { id: 34, nameHanja: '大壯', nameHangul: '대장', fullNameHangul: '뇌천대장', unicodeSymbol: '䷡', upperTrigram: '雷 (우레)', lowerTrigram: '天 (하늘)', natureSummary: '하늘 위에 우레가 울려 퍼져 기세가 드높은 상', coreTheme: '왕성한 힘, 예절과 규범 준수, 무모한 돌진 경계', binary: '111100' },
  35: { id: 35, nameHanja: '晉', nameHangul: '진', fullNameHangul: '화지진', unicodeSymbol: '䷢', upperTrigram: '火 (태양)', lowerTrigram: '地 (땅)', natureSummary: '땅 위로 밝은 태양이 솟아오르는 상', coreTheme: '전진과 도약, 재능의 발휘, 공명정대한 진출', binary: '000101' },
  36: { id: 36, nameHanja: '明夷', nameHangul: '명이', fullNameHangul: '지화명이', unicodeSymbol: '䷣', upperTrigram: '地 (땅)', lowerTrigram: '火 (불)', natureSummary: '밝은 태양이 땅속으로 가라앉아 어두워진 상', coreTheme: '시련과 은인자중, 빛을 감추고 내면의 지혜 보존', binary: '101000' },
  37: { id: 37, nameHanja: '家人', nameHangul: '가인', fullNameHangul: '풍화가인', unicodeSymbol: '䷤', upperTrigram: '風 (바람)', lowerTrigram: '火 (불)', natureSummary: '불에서 바람이 생겨나 집안을 따스하게 덥히는 상', coreTheme: '가정과 내부의 화목, 각자의 본분 지키기, 근본 정립', binary: '101011' },
  38: { id: 38, nameHanja: '睽', nameHangul: '규', fullNameHangul: '화택규', unicodeSymbol: '䷥', upperTrigram: '火 (불)', lowerTrigram: '澤 (연못)', natureSummary: '불은 위로 타오르고 연못물은 아래로 흘러 어긋나는 상', coreTheme: '이견과 반목, 차이 속의 공존 모색, 작은 일부터 풀기', binary: '110101' },
  39: { id: 39, nameHanja: '蹇', nameHangul: '건', fullNameHangul: '수산건', unicodeSymbol: '䷦', upperTrigram: '水 (물/험난)', lowerTrigram: '山 (산)', natureSummary: '험한 물 앞에 가파른 산이 막아서서 발이 묶인 상', coreTheme: '고난과 발걸음의 지체, 멈추어 반성하기, 조력자 찾기', binary: '001010' },
  40: { id: 40, nameHanja: '解', nameHangul: '해', fullNameHangul: '뇌수해', unicodeSymbol: '䷧', upperTrigram: '雷 (우레)', lowerTrigram: '水 (비/물)', natureSummary: '우레와 비가 내린 뒤 얼음이 녹아 풀리는 상', coreTheme: '난관 해결, 관용과 용서, 신속한 정리와 회복', binary: '010100' },
  41: { id: 41, nameHanja: '損', nameHangul: '손', fullNameHangul: '산택손', unicodeSymbol: '䷨', upperTrigram: '山 (산)', lowerTrigram: '澤 (연못)', natureSummary: '연못을 파서 산을 높이듯 아래를 덜어 위를 보태는 상', coreTheme: '사욕의 덜어냄, 절제와 나눔, 장기적 이로움', binary: '110001' },
  42: { id: 42, nameHanja: '益', nameHangul: '익', fullNameHangul: '풍뢰익', unicodeSymbol: '䷩', upperTrigram: '風 (바람)', lowerTrigram: '雷 (우레)', natureSummary: '바람과 우레가 서로를 북돋아 더해주는 상', coreTheme: '풍성한 성장, 선행의 실천, 기회를 포착한 적극적 전진', binary: '100011' },
  43: { id: 43, nameHanja: '夬', nameHangul: '쾌', fullNameHangul: '택천쾌', unicodeSymbol: '䷪', upperTrigram: '澤 (연못)', lowerTrigram: '天 (하늘)', natureSummary: '연못이 하늘 위로 차올라 터져 결단하는 상', coreTheme: '과감한 결단, 악습 척결, 공정하고 온건한 방식', binary: '111110' },
  44: { id: 44, nameHanja: '姤', nameHangul: '구', fullNameHangul: '천풍구', unicodeSymbol: '䷫', upperTrigram: '天 (하늘)', lowerTrigram: '風 (바람)', natureSummary: '하늘 아래 바람이 불어 뜻밖의 만남이 일어나는 상', coreTheme: '우연한 조우, 미세한 변화의 조짐, 유혹에 대한 경계', binary: '011111' },
  45: { id: 45, nameHanja: '萃', nameHangul: '췌', fullNameHangul: '택지췌', unicodeSymbol: '䷬', upperTrigram: '澤 (연못)', lowerTrigram: '地 (땅)', natureSummary: '땅 위에 연못이 모여 물을 모으는 상', coreTheme: '모임과 결집, 정성스러운 구심점, 준비된 축제', binary: '000110' },
  46: { id: 46, nameHanja: '升', nameHangul: '승', fullNameHangul: '지풍승', unicodeSymbol: '䷭', upperTrigram: '地 (땅)', lowerTrigram: '風 (나무/바람)', natureSummary: '땅속에서 나무가 싹을 틔워 점차 위로 자라나는 상', coreTheme: '착실한 상승, 점진적 발전, 조력자의 후원', binary: '011000' },
  47: { id: 47, nameHanja: '困', nameHangul: '곤', fullNameHangul: '택수곤', unicodeSymbol: '䷮', upperTrigram: '澤 (연못)', lowerTrigram: '水 (물)', natureSummary: '연못 아래로 물이 다 빠져나가 메마른 상', coreTheme: '궁지와 시련, 말보다 내실, 침묵 속 굳건한 신념', binary: '010110' },
  48: { id: 48, nameHanja: '井', nameHangul: '정', fullNameHangul: '수풍정', unicodeSymbol: '䷯', upperTrigram: '水 (물)', lowerTrigram: '風 (나무/두레박)', natureSummary: '나무 두레박으로 물을 길어 올리는 샘물의 상', coreTheme: '마르지 않는 원천, 공동체의 지혜, 꾸준한 자기 연마', binary: '011010' },
  49: { id: 49, nameHanja: '革', nameHangul: '혁', fullNameHangul: '택화혁', unicodeSymbol: '䷰', upperTrigram: '澤 (연못)', lowerTrigram: '火 (불)', natureSummary: '연못 속에서 불이 타올라 묵은 가죽을 새롭게 무두질하는 상', coreTheme: '근본적 변혁, 시기의 성숙, 신뢰에 기반한 쇄신', binary: '101110' },
  50: { id: 50, nameHanja: '鼎', nameHangul: '정', fullNameHangul: '화풍정', unicodeSymbol: '䷱', upperTrigram: '火 (불)', lowerTrigram: '風 (나무)', natureSummary: '나무로 불을 지펴 솥에서 새 음식을 끓여내는 상', coreTheme: '새로운 제도의 정립, 인재 양성, 안정적 정착', binary: '011101' },
  51: { id: 51, nameHanja: '震', nameHangul: '진', fullNameHangul: '중뇌진', unicodeSymbol: '䷲', upperTrigram: '雷 (우레)', lowerTrigram: '雷 (우레)', natureSummary: '우레가 백 리를 울리며 세상을 흔드는 상', coreTheme: '경각심과 놀람, 두려움을 통한 자기 수양, 평정심 회복', binary: '100100' },
  52: { id: 52, nameHanja: '艮', nameHangul: '간', fullNameHangul: '중산간', unicodeSymbol: '䷳', upperTrigram: '山 (산)', lowerTrigram: '山 (산)', natureSummary: '첩첩산중처럼 산이 멈추어 솟아 있는 상', coreTheme: '멈춤과 고요, 욕망의 정지, 분수를 지키는 평온', binary: '001001' },
  53: { id: 53, nameHanja: '漸', nameHangul: '점', fullNameHangul: '풍산점', unicodeSymbol: '䷴', upperTrigram: '風 (나무/바람)', lowerTrigram: '山 (산)', natureSummary: '산 위에 나무가 뿌리를 내리며 천천히 자라는 상', coreTheme: '점진적 전진, 단계적 절차, 자연스러운 성숙', binary: '001011' },
  54: { id: 54, nameHanja: '歸妹', nameHangul: '귀매', fullNameHangul: '뇌택귀매', unicodeSymbol: '䷵', upperTrigram: '雷 (우레)', lowerTrigram: '澤 (연못)', natureSummary: '연못 위에 우레가 감정에 휩쓸려 움직이는 상', coreTheme: '충동적인 결합 경계, 순리와 원칙 준수, 신중한 시작', binary: '110100' },
  55: { id: 55, nameHanja: '豐', nameHangul: '풍', fullNameHangul: '뇌화풍', unicodeSymbol: '䷶', upperTrigram: '雷 (우레)', lowerTrigram: '火 (번개)', natureSummary: '우레와 번개가 함께 크게 진동하여 장엄한 상', coreTheme: '정점의 풍요, 그늘에 대한 경계, 공정한 결단', binary: '101100' },
  56: { id: 56, nameHanja: '旅', nameHangul: '려', fullNameHangul: '화산여', unicodeSymbol: '䷷', upperTrigram: '火 (불)', lowerTrigram: '山 (산)', natureSummary: '산 위를 지나가는 불처럼 나그네가 길을 떠나는 상', coreTheme: '여행과 이방인, 신중함과 유연성, 고집 부리지 않음', binary: '001101' },
  57: { id: 57, nameHanja: '巽', nameHangul: '손', fullNameHangul: '중풍손', unicodeSymbol: '䷸', upperTrigram: '風 (바람)', lowerTrigram: '風 (바람)', natureSummary: '바람이 연달아 불어 만물에 부드럽게 스며드는 상', coreTheme: '유순한 스며듦, 겸손한 명령, 지속적인 교화', binary: '011011' },
  58: { id: 58, nameHanja: '兌', nameHangul: '태', fullNameHangul: '중택태', unicodeSymbol: '䷹', upperTrigram: '澤 (연못)', lowerTrigram: '澤 (연못)', natureSummary: '두 연못이 서로 물을 대어주며 기뻐하는 상', coreTheme: '기쁨과 화답, 진실한 대화, 벗과의 학문 연마', binary: '110110' },
  59: { id: 59, nameHanja: '渙', nameHangul: '환', fullNameHangul: '풍수환', unicodeSymbol: '䷺', upperTrigram: '風 (바람)', lowerTrigram: '水 (물)', natureSummary: '물 위에 바람이 불어 얼음이 풀리고 흩어지는 상', coreTheme: '막힘의 해소, 흩어짐과 구심점 회복, 넓은 포용', binary: '010011' },
  60: { id: 60, nameHanja: '節', nameHangul: '절', fullNameHangul: '수택절', unicodeSymbol: '䷻', upperTrigram: '水 (물)', lowerTrigram: '澤 (연못)', natureSummary: '연못 위에 물이 고여 넘치지 않도록 조절하는 상', coreTheme: '마디와 절제, 적절한 규범, 지나친 억압 경계', binary: '110010' },
  61: { id: 61, nameHanja: '中孚', nameHangul: '중부', fullNameHangul: '풍택중부', unicodeSymbol: '䷼', upperTrigram: '風 (바람)', lowerTrigram: '澤 (연못)', natureSummary: '연못 위에 바람이 불어 속마음까지 감응하는 상', coreTheme: '지극한 성실, 마음 중심의 신뢰, 편견 없는 감응', binary: '110011' },
  62: { id: 62, nameHanja: '小過', nameHangul: '소과', fullNameHangul: '뇌산소과', unicodeSymbol: '䷽', upperTrigram: '雷 (우레)', lowerTrigram: '山 (산)', natureSummary: '산 위에 우레가 지나치게 높지 않게 울리는 상', coreTheme: '작은 지나침의 허용, 겸손과 세밀함, 큰일 착수 자제', binary: '001100' },
  63: { id: 63, nameHanja: '旣濟', nameHangul: '기제', fullNameHangul: '수화기제', unicodeSymbol: '䷾', upperTrigram: '水 (물)', lowerTrigram: '火 (불)', natureSummary: '물은 위에 있고 불은 아래에 있어 음식이 알맞게 익은 상', coreTheme: '완성과 성취, 현상 유지의 주의, 나태함과 방심 경계', binary: '101010' },
  64: { id: 64, nameHanja: '未濟', nameHangul: '미제', fullNameHangul: '화수미제', unicodeSymbol: '䷿', upperTrigram: '火 (불)', lowerTrigram: '水 (물)', natureSummary: '불은 위에 있고 물은 아래에 있어 아직 조화를 이루지 못한 상', coreTheme: '미완성과 무한한 가능성, 새로운 출발, 끝없는 정진', binary: '010101' },
};

/**
 * 6개의 효 값(6, 7, 8, 9)을 기반으로 본괘 및 지괘 도출
 */
export function calculateHexagramCast(linesValues: LineValue[]): CastResult {
  if (linesValues.length !== 6) {
    throw new Error("정확히 6개의 효 값이 필요합니다.");
  }

  const lines: LineInfo[] = [];
  let originalBinary = "";
  let transformedBinary = "";
  const changingPositions: number[] = [];

  linesValues.forEach((val, index) => {
    const position = index + 1; // 1 (초효) ~ 6 (상효)
    const isYang = val === 7 || val === 9;
    const isChanging = val === 6 || val === 9;

    lines.push({
      position,
      value: val,
      isYang,
      isChanging,
    });

    if (isChanging) {
      changingPositions.push(position);
    }

    // 본괘 이진값 (양=1, 음=0)
    originalBinary += isYang ? "1" : "0";

    // 지괘 이진값 (동효는 반전)
    if (val === 6) {
      transformedBinary += "1"; // 노음 -> 양
    } else if (val === 9) {
      transformedBinary += "0"; // 노양 -> 음
    } else {
      transformedBinary += isYang ? "1" : "0";
    }
  });

  const originalHexId = HEXAGRAM_BINARY_TO_ID[originalBinary] || 1;
  const transformedHexId = HEXAGRAM_BINARY_TO_ID[transformedBinary] || originalHexId;

  return {
    originalHexId,
    transformedHexId,
    lines,
    changingPositions,
  };
}

/**
 * 동전점 방식 무작위 6효 생성
 */
export function generateRandomCast(): CastResult {
  const values: LineValue[] = [];
  for (let i = 0; i < 6; i++) {
    const rand = Math.random();
    if (rand < 0.125) {
      values.push(6); // 노음 (동효)
    } else if (rand < 0.500) {
      values.push(7); // 소양
    } else if (rand < 0.875) {
      values.push(8); // 소음
    } else {
      values.push(9); // 노양 (동효)
    }
  }
  return calculateHexagramCast(values);
}
