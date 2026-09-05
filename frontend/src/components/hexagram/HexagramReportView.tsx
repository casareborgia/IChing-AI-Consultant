'use client';

import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Compass, Sparkles, Copy, Check, ArrowRight, ShieldAlert, Lightbulb, BookOpen, Layers, ChevronDown, ChevronUp } from 'lucide-react';
import { CastResult, ChatMessage, HexagramReportData } from '../../types/iching';
import { HEXAGRAMS_META } from '../../data/hexagramsData';
import { HexagramSymbol } from './HexagramSymbol';

interface HexagramReportViewProps {
  castResult: CastResult;
  userQuestion: string;
  firstMessage?: ChatMessage;
  reportData?: HexagramReportData;
  onProceedToCounsel: () => void;
}

export const HexagramReportView: React.FC<HexagramReportViewProps> = ({
  castResult,
  userQuestion,
  firstMessage,
  reportData,
  onProceedToCounsel,
}) => {
  const [copied, setCopied] = useState(false);
  const [showTechnicalDetails, setShowTechnicalDetails] = useState(true);

  const originalMeta = HEXAGRAMS_META[castResult.originalHexId];
  const transformedMeta = HEXAGRAMS_META[castResult.transformedHexId];
  const hasTransformation = castResult.changingPositions.length > 0;

  // 지괘 라인
  const transformedLines = castResult.lines.map((l) => {
    if (l.value === 6) return { ...l, isYang: true, isChanging: false, value: 7 as const };
    if (l.value === 9) return { ...l, isYang: false, isChanging: false, value: 8 as const };
    return { ...l, isChanging: false };
  });

  // 동효 위치 텍스트
  const changingLinesText = hasTransformation
    ? castResult.changingPositions.map((pos) => `${pos}효`).join(', ')
    : '불변 (동효 없음)';

  // 초점 효사/괘사 명칭
  const focusTargetName = castResult.focusRule?.targetLineNumbers?.length
    ? `${originalMeta.fullNameHangul} 괘 ${castResult.focusRule.targetLineNumbers.map((n) => `${n}효`).join(', ')}`
    : `${originalMeta.fullNameHangul} 괘사`;

  const focusRuleDesc = castResult.focusRule?.descriptionKo
    ? castResult.focusRule.descriptionKo
    : `${originalMeta.fullNameHangul}의 본래 괘상과 상징 흐름에 집중합니다.`;

  // === 4단계 완벽 리포트 데이터 바인딩 (LLM 전용 reportData 최우선) ===
  
  // 1. 질문 및 마음가짐 세팅
  const part1Question = reportData?.question_setting.question || userQuestion;
  const part1Mindset = reportData?.question_setting.mindset_rule || 
    '질문자는 삿된 사리사욕이나 무분별한 호기심을 비우고, 무념무상의 경건한 마음으로 단 한 번만 점을 치는 재삼덕 금기 원칙을 준수하며 점을 쳤습니다.';

  // 2. 괘 도출 과정
  const linesCastingList = reportData?.hexagram_casting.lines || castResult.lines.map((l, idx) => {
    const pos = idx + 1;
    const isChanging = castResult.changingPositions.includes(pos);
    let typeKo = '소양', sym = '⚊', note = '변하지 않는 양효';
    if (l.value === 8) { typeKo = '소음'; sym = '⚋'; note = '변하지 않는 음효'; }
    if (l.value === 9) { typeKo = '노양'; sym = '⚊○'; note = '동효(변효) (양에서 음으로 변함)'; }
    if (l.value === 6) { typeKo = '노음'; sym = '⚋✕'; note = '동효(변효) (음에서 양으로 변함)'; }
    return { position: pos, name: `${pos}효`, value: l.value, line_type_ko: typeKo, symbol: sym, is_changing: isChanging, note };
  });

  const origNameFull = reportData?.hexagram_casting.original_name_full || originalMeta.fullNameHangul;
  const origNameHanja = reportData?.hexagram_casting.original_name_hanja || originalMeta.nameHanja;
  const origSummary = reportData?.hexagram_casting.original_summary || originalMeta.natureSummary;

  const transNameFull = reportData?.hexagram_casting.transformed_name_full || transformedMeta.fullNameHangul;
  const transNameHanja = reportData?.hexagram_casting.transformed_name_hanja || transformedMeta.nameHanja;
  const transSummary = reportData?.hexagram_casting.transformed_summary || transformedMeta.natureSummary;

  // 3. 고변점 및 체용
  const ruleDesc = reportData?.focus_and_body_use.rule_description || focusRuleDesc;
  const primaryTargetName = reportData?.focus_and_body_use.primary_target_name || focusTargetName;
  const bodyUseFlow = reportData?.focus_and_body_use.body_use_flow || 
    `본괘(${origNameFull}): 현재 질문자께서 직면한 대전제(體) ➡ [${originalMeta.coreTheme}]의 기류 속에 있습니다.\n지괘(${transNameFull}): 변화 이후 다다를 지향점(用) ➡ [${transformedMeta.coreTheme}]의 방향으로 내실을 다져가야 합니다.`;

  // 4. 괘사·효사 종합 해석 및 실질적 조언
  const sec1 = reportData?.section1_diagnosis || {
    title: `① 현재 상황 진단 (본괘: ${origNameFull})`,
    target_name: origNameFull,
    hanja_text: origNameHanja,
    interpretation: `현재 질문자님의 사연("${userQuestion}")은 '${origNameFull}'가 상징하는 "${origSummary}"의 시공간적 상황에 발을 딛고 있습니다. '${originalMeta.coreTheme}'의 이치를 인지하고 현 위치의 본질을 바로 보아야 합니다.`
  };

  const sec2 = reportData?.section2_action || {
    title: `② 핵심 행동 지침 (주 주요 해석 대상: ${primaryTargetName})`,
    target_name: primaryTargetName,
    hanja_text: null,
    interpretation: `${primaryTargetName}의 가르침은 고민하시는 사연에 대해 '${originalMeta.coreTheme}'의 도리에 따라 외부 수식어보다 내면의 진실함과 올바른 명분을 먼저 세울 것을 조언합니다.`
  };

  const sec3 = reportData?.section3_warning || {
    title: `③ 보조 경계 지침 (${hasTransformation ? `함께 동한 ${changingLinesText}` : '불변괘 경계 지침'})`,
    target_name: hasTransformation ? changingLinesText : `${origNameFull} 경계 지침`,
    hanja_text: null,
    interpretation: hasTransformation
      ? `'${origNameFull}' 괘에서 동한 ${changingLinesText}의 변화에 따라, 현 시점에서는 성급한 주관적 무리수를 삼가고 추진 전 계획의 타당성을 다각도로 객관 검증해야 합니다.`
      : `'${origNameFull}' 괘가 경계하는 핵심 바는 '${originalMeta.coreTheme}'의 중심을 잃고 조급해지는 것입니다. 내담자님의 사연("${userQuestion}")에 대해 이 괘가 전하는 본래의 바른 덕목을 흔들림 없이 지켜내십시오.`
  };

  const sec4 = reportData?.section4_future || {
    title: `④ 미래의 귀결 및 주의점 (${hasTransformation ? `지괘: ${transNameFull}` : `본괘 유지: ${origNameFull}`})`,
    target_name: hasTransformation ? transNameFull : origNameFull,
    hanja_text: null,
    interpretation: hasTransformation
      ? `변화 이후 다다를 지괘는 '${transNameFull}'의 이치를 지닙니다. "${transSummary}"의 상징처럼 내실을 정비하고 안정적으로 연착륙하는 것이 성공의 핵심입니다.`
      : `'${origNameFull}'의 굳건한 이치를 온전히 지켜나간다면 "${origSummary}"의 순리를 얻어 안정을 다지고 결실을 다지게 됩니다.`
  };

  const finalSummaryText = reportData?.final_summary || 
    `"${origNameFull} 괘의 핵심 이치인 '${originalMeta.coreTheme}'에 따라 내담자님의 사연을 성찰하되, 성급함을 삼가고 내실을 다지십시오. ${hasTransformation ? `이후 마주할 지괘(${transNameFull})의 지혜처럼 내부 역량을 정비하는 것이 승리의 열쇠입니다.` : `현재 괘의 본래 중심을 굳건히 지키는 것이 해법입니다.`}"`;

  // 마크다운 원문 복사 구성
  const markdownText = `1. 질문 및 마음가짐 세팅 (사례 설정)
질문자의 고민: "${part1Question}"
점서 예식: ${part1Mindset}

2. 괘 도출 과정 (수리 도출 및 효 쌓기)
${linesCastingList.map((l) => `${l.name}: ${l.value} (${l.line_type_ko}, ${l.symbol}) ➡ ${l.note}`).join('\n')}

① 본괘(本卦)의 성립
도출된 본괘: ${origNameFull}(${origNameHanja})
의미: '${origSummary}'을 상징합니다.

② 변효(動爻) 및 지괘(之卦)의 도출
${hasTransformation ? `동효 위치: ${changingLinesText}\n도출된 지괘: ${transNameFull}(${transNameHanja})\n의미: '${transSummary}'을 상징합니다.` : '변효가 발생하지 않은 불변괘입니다.'}

3. 고변점(考變占) 및 체용(體用) 해석 규칙 적용
변효 개수별 규칙 (${linesCastingList.filter(l => l.is_changing).length}개 변효):
${ruleDesc}

체(體)와 용(用)의 흐름:
${bodyUseFlow}

4. 괘사·효사 종합 해석 및 실질적 조언

${sec1.title}
${sec1.hanja_text ? `원문: ${sec1.hanja_text}\n` : ''}해석: ${sec1.interpretation}

${sec2.title}
${sec2.hanja_text ? `원문: ${sec2.hanja_text}\n` : ''}해석: ${sec2.interpretation}

${sec3.title}
${sec3.hanja_text ? `원문: ${sec3.hanja_text}\n` : ''}해석: ${sec3.interpretation}

${sec4.title}
${sec4.hanja_text ? `원문: ${sec4.hanja_text}\n` : ''}해석: ${sec4.interpretation}

💡 질문자에 대한 최종 종합 컨설팅 요약
"${finalSummaryText}"
`;

  const handleCopy = () => {
    navigator.clipboard.writeText(markdownText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -15 }}
      transition={{ duration: 0.4 }}
      className="w-full max-w-4xl sm:max-w-5xl mx-auto py-6 space-y-8"
    >
      {/* 4단계 고품격 컨설팅 리포트 메인 컨테이너 */}
      <div className="bg-stone-900/95 border border-amber-500/40 rounded-3xl p-6 sm:p-10 shadow-2xl backdrop-blur-md text-stone-100 relative overflow-hidden space-y-10">
        
        {/* 상단 최상위 헤더 & 복사 버튼 */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between border-b border-stone-800 pb-5 gap-3">
          <div className="space-y-1">
            <div className="flex items-center gap-2 text-xs sm:text-sm font-serif tracking-widest text-amber-400">
              <Compass className="w-4 h-4 sm:w-5 sm:h-5 text-amber-400" />
              <span className="font-bold uppercase tracking-wider">주역 수석 AI 1:1 심층 성찰 보고서</span>
            </div>
            <p className="text-xs sm:text-sm text-stone-400 font-light">
              고전 원문(정전·본의)과 송대 고변점 룰 기반의 100% 1:1 사연 맞춤형 가변 리포트
            </p>
          </div>

          <button
            onClick={handleCopy}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-stone-800 hover:bg-stone-700 text-amber-300 text-xs sm:text-sm transition cursor-pointer border border-stone-700 shadow-md font-medium shrink-0"
            title="4단계 예시 서식 마크다운 전체 복사"
          >
            {copied ? (
              <>
                <Check className="w-4 h-4 text-emerald-400" />
                <span className="text-emerald-400 font-bold">리포트 복사 완료</span>
              </>
            ) : (
              <>
                <Copy className="w-4 h-4 text-amber-400" />
                <span>마크다운 전문 복사</span>
              </>
            )}
          </button>
        </div>

        {/* 접기/펼치기 제어 스위치 & 기술 메타 카드 */}
        <div className="space-y-4">
          <button
            onClick={() => setShowTechnicalDetails(!showTechnicalDetails)}
            className="w-full flex items-center justify-between p-4 rounded-2xl bg-stone-950/80 border border-stone-800/90 text-amber-300 text-sm font-serif font-bold hover:bg-stone-950 transition cursor-pointer"
          >
            <div className="flex items-center gap-2.5">
              <Layers className="w-4 h-4 text-amber-400" />
              <span>1~3단계 괘 도출 수리 및 체용(體用) 적용 근거</span>
            </div>
            <div className="flex items-center gap-1 text-xs font-normal text-stone-400">
              <span>{showTechnicalDetails ? '요약 접기' : '자세히 보기'}</span>
              {showTechnicalDetails ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </div>
          </button>

          {showTechnicalDetails && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className="space-y-4 pt-1"
            >
              {/* 1. 질문 및 마음가짐 세팅 */}
              <div className="space-y-3 bg-stone-950/60 p-5 rounded-2xl border border-stone-800/80">
                <div className="flex items-center gap-2 text-sm sm:text-base font-serif font-bold text-amber-300">
                  <span className="bg-amber-500 text-stone-950 text-xs font-mono px-2.5 py-0.5 rounded font-bold">1</span>
                  <span>질문 및 마음가짐 세팅</span>
                </div>
                <div className="text-sm sm:text-base text-stone-200 leading-relaxed space-y-2 font-light">
                  <p><strong className="text-amber-400 font-medium">질문자의 고민:</strong> &ldquo;{part1Question}&rdquo;</p>
                  <p><strong className="text-stone-400 font-medium">점서 예식:</strong> {part1Mindset}</p>
                </div>
              </div>

              {/* 2. 괘 도출 과정 (수리 도출 및 효 쌓기) */}
              <div className="space-y-3 bg-stone-950/60 p-5 rounded-2xl border border-stone-800/80">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-sm sm:text-base font-serif font-bold text-amber-300">
                    <span className="bg-amber-500 text-stone-950 text-xs font-mono px-2.5 py-0.5 rounded font-bold">2</span>
                    <span>괘 도출 과정 (수리 도출 및 효 쌓기)</span>
                  </div>
                  <span className="text-xs text-amber-400/80 font-mono">초효 ➔ 상효 수리 산출</span>
                </div>

                {/* 6효 수리 표 현황 */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 text-xs sm:text-sm font-mono pt-1">
                  {linesCastingList.map((l) => (
                    <div
                      key={l.position}
                      className={`p-3 rounded-xl flex items-center justify-between border ${
                        l.is_changing
                          ? 'bg-amber-950/40 border-amber-500/60 text-amber-200 font-bold shadow-sm'
                          : 'bg-stone-900/70 border-stone-800 text-stone-300'
                      }`}
                    >
                      <span>{l.name}: <strong className="text-amber-400">{l.value}</strong> ({l.line_type_ko}, {l.symbol})</span>
                      <span className="text-xs opacity-90">{l.note}</span>
                    </div>
                  ))}
                </div>

                {/* 본괘 / 지괘 도출 칩 현황 */}
                <div className="pt-2 grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="p-4 rounded-xl bg-stone-900/90 border border-amber-500/40 flex items-center gap-4 shadow">
                    <HexagramSymbol lines={castResult.lines} size="sm" />
                    <div>
                      <span className="text-sm text-amber-400 font-serif block font-bold">① 본괘: {origNameFull} ({origNameHanja})</span>
                      <span className="text-xs sm:text-sm text-stone-200 font-light leading-snug block mt-1">{origSummary}</span>
                    </div>
                  </div>

                  {hasTransformation ? (
                    <div className="p-4 rounded-xl bg-stone-900/90 border border-stone-700 flex items-center gap-4 shadow">
                      <HexagramSymbol lines={transformedLines} size="sm" />
                      <div>
                        <span className="text-sm text-stone-300 font-serif block font-bold">② 지괘: {transNameFull} ({transNameHanja})</span>
                        <span className="text-xs sm:text-sm text-stone-400 font-light leading-snug block mt-1">{transSummary}</span>
                      </div>
                    </div>
                  ) : (
                    <div className="p-4 rounded-xl bg-stone-900/40 border border-stone-800 flex items-center text-xs sm:text-sm text-stone-400 italic">
                      변효가 발생하지 않은 굳건한 불변괘(不變卦)입니다.
                    </div>
                  )}
                </div>
              </div>

              {/* 3. 고변점 및 체용 해석 규칙 적용 */}
              <div className="space-y-3 bg-stone-950/60 p-5 rounded-2xl border border-stone-800/80">
                <div className="flex items-center gap-2 text-sm sm:text-base font-serif font-bold text-amber-300">
                  <span className="bg-amber-500 text-stone-950 text-xs font-mono px-2.5 py-0.5 rounded font-bold">3</span>
                  <span>고변점(考變占) 및 체용(體用) 해석 규칙 적용</span>
                </div>
                <div className="text-sm sm:text-base text-stone-200 leading-relaxed space-y-2.5 font-light">
                  <p><strong className="text-amber-400 font-medium">변효 개수별 규칙:</strong> {ruleDesc}</p>
                  <div className="p-4 rounded-xl bg-stone-900/80 border border-stone-800 text-stone-200 space-y-1.5">
                    <strong className="text-amber-300 text-xs sm:text-sm font-serif block font-bold">체(體)와 용(用)의 흐름:</strong>
                    <p className="whitespace-pre-line text-xs sm:text-sm font-light leading-relaxed">{bodyUseFlow}</p>
                  </div>
                </div>
              </div>
            </motion.div>
          )}
        </div>

        {/* 4. 괘사·효사 종합 해석 및 실질적 조언 (시원시원한 에디토리얼 가독성 스타일) */}
        <div className="space-y-8 pt-2">
          <div className="flex items-center gap-3 border-b-2 border-amber-500/40 pb-3">
            <span className="bg-amber-500 text-stone-950 text-sm font-mono px-3 py-1 rounded-lg font-extrabold shadow">4</span>
            <h2 className="text-lg sm:text-xl font-serif font-bold text-amber-200 tracking-tight">
              괘사·효사 종합 해석 및 실질적 조언
            </h2>
          </div>

          {/* ① 현재 상황 진단 */}
          <div className="space-y-3 p-6 sm:p-7 rounded-2xl bg-stone-950/70 border border-stone-800 shadow-lg transition hover:border-stone-700">
            <h3 className="text-base sm:text-lg font-serif font-bold text-amber-300 flex items-center gap-2">
              <span className="text-amber-500 font-mono text-sm">①</span>
              <span>{sec1.title}</span>
            </h3>
            {sec1.hanja_text && (
              <div className="p-3.5 rounded-xl bg-amber-950/30 border border-amber-500/40 text-amber-200 font-serif text-sm sm:text-base leading-relaxed tracking-wide">
                <strong className="text-amber-400 font-bold block text-xs font-mono uppercase mb-1">고전 원문:</strong>
                {sec1.hanja_text}
              </div>
            )}
            <p className="text-sm sm:text-base text-stone-100 leading-loose font-light whitespace-pre-line pt-1">
              {sec1.interpretation}
            </p>
          </div>

          {/* ② 핵심 행동 지침 (가장 중요한 핵심 강조 박스) */}
          <div className="space-y-4 p-6 sm:p-7 rounded-2xl bg-gradient-to-b from-amber-950/30 via-stone-950/80 to-amber-950/20 border-2 border-amber-500/50 shadow-xl relative overflow-hidden">
            <div className="flex items-center gap-2 text-xs sm:text-sm text-amber-400 font-bold tracking-wider uppercase">
              <BookOpen className="w-4 h-4 text-amber-400" />
              <span>주 주요 해석 대상 1:1 맞춤 지침</span>
            </div>

            <h3 className="text-base sm:text-xl font-serif font-bold text-amber-200">
              {sec2.title}
            </h3>

            {sec2.hanja_text && (
              <div className="p-4 rounded-xl bg-stone-900/90 border border-amber-500/50 text-amber-200 font-serif text-base sm:text-lg leading-relaxed shadow-inner">
                <strong className="text-amber-400 font-bold block text-xs font-mono uppercase mb-1.5">핵심 효사/괘사 원문:</strong>
                {sec2.hanja_text}
              </div>
            )}

            <p className="text-sm sm:text-base text-amber-50 leading-loose font-light whitespace-pre-line pt-2">
              {sec2.interpretation}
            </p>
          </div>

          {/* ③ 보조 경계 지침 */}
          <div className="space-y-3 p-6 sm:p-7 rounded-2xl bg-stone-950/70 border border-stone-800 shadow-lg transition hover:border-stone-700">
            <div className="flex items-center gap-2 text-xs sm:text-sm text-amber-400 font-semibold mb-1">
              <ShieldAlert className="w-4 h-4 text-amber-500" />
              <span>경계 및 삼가기 조언</span>
            </div>
            <h3 className="text-base sm:text-lg font-serif font-bold text-amber-300">
              {sec3.title}
            </h3>
            {sec3.hanja_text && (
              <div className="p-3.5 rounded-xl bg-amber-950/30 border border-amber-500/40 text-amber-200 font-serif text-sm sm:text-base leading-relaxed tracking-wide">
                <strong className="text-amber-400 font-bold block text-xs font-mono uppercase mb-1">경계 효사 원문:</strong>
                {sec3.hanja_text}
              </div>
            )}
            <p className="text-sm sm:text-base text-stone-200 leading-loose font-light whitespace-pre-line pt-1">
              {sec3.interpretation}
            </p>
          </div>

          {/* ④ 미래의 귀결 및 주의점 */}
          <div className="space-y-3 p-6 sm:p-7 rounded-2xl bg-stone-950/70 border border-stone-800 shadow-lg transition hover:border-stone-700">
            <h3 className="text-base sm:text-lg font-serif font-bold text-amber-300">
              {sec4.title}
            </h3>
            {sec4.hanja_text && (
              <div className="p-3.5 rounded-xl bg-amber-950/30 border border-amber-500/40 text-amber-200 font-serif text-sm sm:text-base leading-relaxed tracking-wide">
                <strong className="text-amber-400 font-bold block text-xs font-mono uppercase mb-1">지괘 원문 및 대상전:</strong>
                {sec4.hanja_text}
              </div>
            )}
            <p className="text-sm sm:text-base text-stone-200 leading-loose font-light whitespace-pre-line pt-1">
              {sec4.interpretation}
            </p>
          </div>
        </div>

        {/* 💡 질문자에 대한 최종 종합 컨설팅 요약 (럭셔리 하이라이트) */}
        <div className="p-6 sm:p-8 rounded-3xl bg-gradient-to-r from-amber-950/70 via-stone-900 to-amber-950/60 border-2 border-amber-500/70 shadow-2xl space-y-4">
          <div className="flex items-center gap-2.5 text-base sm:text-lg font-serif font-bold text-amber-300">
            <Lightbulb className="w-6 h-6 text-amber-400 shrink-0 animate-pulse" />
            <span>💡 질문자에 대한 최종 종합 컨설팅 요약</span>
          </div>
          <div className="text-sm sm:text-lg text-amber-50 font-medium leading-loose italic border-l-4 border-amber-400 pl-5 whitespace-pre-line">
            &ldquo;{finalSummaryText}&rdquo;
          </div>
        </div>

        {/* 하단 상담 진행 버튼 (크고 명확한 액션 버튼) */}
        <div className="pt-6 border-t border-stone-800 flex flex-col sm:flex-row items-center justify-between gap-5">
          <span className="text-xs sm:text-sm text-stone-400 font-light text-center sm:text-left">
            종합 컨설팅 리포트를 숙고하신 후, 수석 AI 상담사와 1:1 심층 질의응답을 진행하세요.
          </span>

          <button
            onClick={onProceedToCounsel}
            className="w-full sm:w-auto px-8 py-4 rounded-2xl bg-gradient-to-r from-amber-500 to-amber-400 hover:from-amber-400 hover:to-amber-300 text-stone-950 font-bold text-base transition-all shadow-xl shadow-amber-950/60 flex items-center justify-center gap-2.5 cursor-pointer active:scale-[0.98] shrink-0"
          >
            <span>상담 진행하기</span>
            <ArrowRight className="w-5 h-5" />
          </button>
        </div>

      </div>
    </motion.div>
  );
};
