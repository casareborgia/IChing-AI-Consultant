'use client';

import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Compass, Sparkles, Copy, Check, ArrowRight, ShieldAlert, Lightbulb, BookOpen } from 'lucide-react';
import { CastResult, ChatMessage } from '../../types/iching';
import { HEXAGRAMS_META } from '../../data/hexagramsData';
import { HexagramSymbol } from './HexagramSymbol';

interface HexagramReportViewProps {
  castResult: CastResult;
  userQuestion: string;
  firstMessage?: ChatMessage;
  onProceedToCounsel: () => void;
}

export const HexagramReportView: React.FC<HexagramReportViewProps> = ({
  castResult,
  userQuestion,
  firstMessage,
  onProceedToCounsel,
}) => {
  const [copied, setCopied] = useState(false);

  const originalMeta = HEXAGRAMS_META[castResult.originalHexId];
  const transformedMeta = HEXAGRAMS_META[castResult.transformedHexId];
  const hasTransformation = castResult.changingPositions.length > 0;

  // 지괘 라인
  const transformedLines = castResult.lines.map((l) => {
    if (l.value === 6) return { ...l, isYang: true, isChanging: false, value: 7 as const };
    if (l.value === 9) return { ...l, isYang: false, isChanging: false, value: 8 as const };
    return { ...l, isChanging: false };
  });

  // 동효 위치 텍스트 (예: 3효, 5효)
  const changingLinesText = hasTransformation
    ? castResult.changingPositions.map((pos) => `${pos}효`).join(', ')
    : '불변 (동효 없음)';

  // 초점 효사/괘사 명칭 (예: 수천수 괘 3효 또는 수천수 괘사)
  const focusTargetName = castResult.focusRule?.targetLineNumbers?.length
    ? `${originalMeta.fullNameHangul} 괘 ${castResult.focusRule.targetLineNumbers.map((n) => `${n}효`).join(', ')}`
    : `${originalMeta.fullNameHangul} 괘사`;

  // 주자 고변점 초점 설명 (실제 DB 및 룰 엔진 결과)
  const focusRuleDesc = castResult.focusRule?.descriptionKo
    ? castResult.focusRule.descriptionKo
    : `${originalMeta.fullNameHangul}의 본래 괘상과 상징 흐름에 집중합니다.`;

  // 백엔드 AI 1턴 메시지 및 단락 분할 (사연 맞춤형 AI 문장 추출)
  const aiContent = (firstMessage?.content || '').trim();
  const paragraphs = aiContent ? aiContent.split('\n\n').filter((p) => p.trim()) : [];
  
  const aiDiagnosisPara = paragraphs[0] || '';
  const aiActionPara = paragraphs[1] || '';
  const aiWarningPara = paragraphs[2] || '';
  const aiFuturePara = paragraphs.slice(3).join('\n\n') || '';

  const evidences = firstMessage?.evidences || [];
  const evidenceText = evidences.length > 0
    ? evidences.map((e) => `• [${e.sourceTitle}] ${e.content}`).join('\n')
    : '';

  // --- 100% 동적 사연/괘 맞춤형 5대 섹션 구성 ---

  // ① 현재 상황 진단 (본괘)
  const section1Diagnosis = `${originalMeta.fullNameHangul}(${originalMeta.nameHanja}) 괘는 상괘(${originalMeta.upperTrigram})와 하괘(${originalMeta.lowerTrigram})가 어우러져 "${originalMeta.natureSummary}"의 형상을 보입니다.\n\n${aiDiagnosisPara ? `[상황 진단] ${aiDiagnosisPara}` : `현재 사연("${userQuestion}")은 ${originalMeta.coreTheme}의 시공간적 기류 속에 놓여 있으므로, 섣부른 판단보다는 상황의 본질을 깊이 들여다보아야 합니다.`}`;

  // ② 핵심 행동 지침 (주 주요 해석 대상)
  const section2Action = `• 주요 해석 대상: ${focusTargetName}
• 고변점 지침: ${focusRuleDesc}
${castResult.focusRule?.bodyUseNoteKo ? `• 체용(體用) 참작: ${castResult.focusRule.bodyUseNoteKo}\n` : ''}
${aiActionPara ? `[행동 지침] ${aiActionPara}` : `${originalMeta.fullNameHangul}의 이치에 따라 조급한 이익이나 외형보다는 본질적 신뢰와 굳건한 태도를 먼저 다지는 것이 핵심 실천 방향입니다.`}
${evidenceText ? `\n\n[고전 주석 근거]\n${evidenceText}` : ''}`;

  // ③ 보조 경계 지침 (동효 및 경계)
  const section3Warning = hasTransformation
    ? `동효(${changingLinesText})가 움직인 것은 조급한 무리수나 성급한 확장, 독단적인 추진을 삼가라는 강한 경고입니다.\n\n${aiWarningPara ? `[경계 지침] ${aiWarningPara}` : `실행에 옮기기 전 현실적인 조건과 위험 요인을 최소 두세 번 이상 신중히 점검한 뒤 나아가십시오.`}`
    : `불변괘의 경계 지침은 섣부른 조급함을 버리고 현재의 중심을 차분히 지키는 것입니다.\n\n${aiWarningPara ? `[경계 지침] ${aiWarningPara}` : `무리한 변화보다는 내부 내실을 다지는 데 집중하십시오.`}`;

  // ④ 미래의 귀결 및 주의점 (지괘)
  const section4Future = hasTransformation
    ? `[지괘: ${transformedMeta.fullNameHangul}(${transformedMeta.nameHanja})]
전환을 거친 뒤 다다를 지괘는 '${transformedMeta.coreTheme}'의 성격을 가진 ${transformedMeta.fullNameHangul} 괘입니다.\n\n${aiFuturePara ? `[미래 귀결] ${aiFuturePara}` : `변화 후에는 외형을 마구 확장하기보다 "${transformedMeta.natureSummary}"의 이치처럼 내부 역량을 정비하고 절제하며 내실을 양육해야 온전한 결실을 맺게 됩니다.`}`
    : `[본괘 유지: ${originalMeta.fullNameHangul}(${originalMeta.nameHanja})]
현재 괘의 상징처럼 조급함 없이 내실을 다져나가면 "${originalMeta.natureSummary}"의 순리를 얻어 점진적이고 안정적인 성취를 이루게 됩니다.`;

  // 💡 질문자에 대한 최종 종합 컨설팅 요약
  const section5Summary = `"${originalMeta.fullNameHangul}의 흐름 속에서 고민하시는 성찰의 방향은 정당합니다. 다만 조급한 성급함을 경계하고 **계획과 실행 조건을 최소 세 번 이상 신중히 재검증**하십시오. ${hasTransformation ? `이후 다다를 지괘(${transformedMeta.fullNameHangul})의 가르침처럼 **대규모 무리한 확장보다는 내부 역량 정비와 내실 양육에 집중**하는 것이 최선의 길입니다.` : `현재 괘의 가르침처럼 **내실 다지기와 굳건한 신뢰 확보에 집중**하는 것이 가장 지혜로운 열쇠입니다.`}"`;

  // 마크다운 복사용 원문 텍스트
  const markdownText = `4. 괘사·효사 종합 해석 및 실질적 조언

① 현재 상황 진단 (본괘: ${originalMeta.fullNameHangul})
${section1Diagnosis}

② 핵심 행동 지침 (주 주요 해석 대상: ${focusTargetName})
${section2Action}

③ 보조 경계 지침 (${hasTransformation ? `함께 동한 ${changingLinesText}` : '경계 지침'})
${section3Warning}

④ 미래의 귀결 및 주의점 (${hasTransformation ? `지괘: ${transformedMeta.fullNameHangul}` : `본괘: ${originalMeta.fullNameHangul}`})
${section4Future}

💡 질문자에 대한 최종 종합 컨설팅 요약
${section5Summary}
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
      className="w-full max-w-3xl mx-auto py-4 space-y-6"
    >
      {/* 괘해석리포트 메인 카드 컨테이너 */}
      <div className="bg-stone-900/95 border border-amber-500/40 rounded-2xl p-5 sm:p-8 shadow-2xl backdrop-blur-md text-stone-100 relative overflow-hidden space-y-6">
        {/* 상단 뱃지 & 마크다운 복사 버튼 */}
        <div className="flex items-center justify-between border-b border-stone-800 pb-4">
          <div className="flex items-center gap-2 text-xs font-serif tracking-wider text-amber-400">
            <Compass className="w-4 h-4 text-amber-400" />
            <span className="font-semibold uppercase">주역 심층 성찰 리포트</span>
          </div>

          <button
            onClick={handleCopy}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-stone-800 hover:bg-stone-700 text-stone-300 text-xs transition cursor-pointer border border-stone-700"
            title="마크다운 리포트 원문 복사"
          >
            {copied ? (
              <>
                <Check className="w-3.5 h-3.5 text-emerald-400" />
                <span className="text-emerald-400 font-medium">복사 완료</span>
              </>
            ) : (
              <>
                <Copy className="w-3.5 h-3.5 text-stone-400" />
                <span>MD 복사</span>
              </>
            )}
          </button>
        </div>

        {/* 메인 타이틀 헤더 */}
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-xs text-amber-400/90 font-mono">
            <Sparkles className="w-3.5 h-3.5" />
            <span>고전 주석 및 괘효사 통합 컨설팅</span>
          </div>
          <h1 className="text-xl sm:text-2xl font-serif font-bold text-amber-200 leading-snug">
            4. 괘사·효사 종합 해석 및 실질적 조언
          </h1>
          <p className="text-xs text-stone-400 font-light italic">
            내담자 사연: &ldquo;{userQuestion}&rdquo;
          </p>
        </div>

        {/* 괘상 심볼 바인딩 칩 */}
        <div className="p-4 rounded-xl bg-stone-950/70 border border-stone-800 flex items-center justify-around">
          <div className="flex flex-col items-center">
            <span className="text-xs text-amber-400 font-serif mb-1.5">[본괘] {originalMeta.fullNameHangul} ({originalMeta.nameHanja})</span>
            <HexagramSymbol lines={castResult.lines} size="sm" />
          </div>

          {hasTransformation && (
            <>
              <ArrowRight className="w-5 h-5 text-amber-500" />
              <div className="flex flex-col items-center">
                <span className="text-xs text-stone-400 font-serif mb-1.5">[지괘] {transformedMeta.fullNameHangul} ({transformedMeta.nameHanja})</span>
                <HexagramSymbol lines={transformedLines} size="sm" />
              </div>
            </>
          )}
        </div>

        {/* ① 현재 상황 진단 (본괘) */}
        <div className="space-y-2">
          <h2 className="text-base sm:text-lg font-serif font-semibold text-amber-300 flex items-center gap-2 border-b border-stone-800 pb-2">
            <span className="text-amber-500 font-mono text-sm">①</span> 현재 상황 진단 <span className="text-xs text-stone-400 font-normal">(본괘: {originalMeta.fullNameHangul})</span>
          </h2>
          <div className="p-4 rounded-xl bg-stone-950/60 border border-stone-800/80 text-xs sm:text-sm text-stone-200 leading-relaxed font-light whitespace-pre-line">
            {section1Diagnosis}
          </div>
        </div>

        {/* ② 핵심 행동 지침 (주 주요 해석 대상) */}
        <div className="space-y-2">
          <h2 className="text-base sm:text-lg font-serif font-semibold text-amber-300 flex items-center gap-2 border-b border-stone-800 pb-2">
            <span className="text-amber-500 font-mono text-sm">②</span> 핵심 행동 지침 <span className="text-xs text-stone-400 font-normal">(주 주요 해석 대상: {focusTargetName})</span>
          </h2>
          <div className="p-4 rounded-xl bg-amber-950/20 border border-amber-500/30 text-xs sm:text-sm text-amber-100/90 leading-relaxed space-y-2">
            <div className="flex items-center gap-1.5 text-xs text-amber-400 font-semibold">
              <BookOpen className="w-4 h-4" />
              <span>초점 고변점 및 이치 풀이</span>
            </div>
            <div className="whitespace-pre-line text-stone-200 font-light">
              {section2Action}
            </div>
          </div>
        </div>

        {/* ③ 보조 경계 지침 */}
        <div className="space-y-2">
          <h2 className="text-base sm:text-lg font-serif font-semibold text-amber-300 flex items-center gap-2 border-b border-stone-800 pb-2">
            <span className="text-amber-500 font-mono text-sm">③</span> 보조 경계 지침 <span className="text-xs text-stone-400 font-normal">({hasTransformation ? `함께 동한 ${changingLinesText}` : '경계 주의점'})</span>
          </h2>
          <div className="p-4 rounded-xl bg-stone-950/60 border border-stone-800/80 text-xs sm:text-sm text-stone-300 leading-relaxed">
            <div className="flex items-center gap-1.5 text-xs text-amber-400/90 font-medium mb-1.5">
              <ShieldAlert className="w-4 h-4 text-amber-500" />
              <span>삼가고 바로잡을 경계 조언</span>
            </div>
            <div className="text-stone-300 font-light whitespace-pre-line">
              {section3Warning}
            </div>
          </div>
        </div>

        {/* ④ 미래의 귀결 및 주의점 (지괘) */}
        <div className="space-y-2">
          <h2 className="text-base sm:text-lg font-serif font-semibold text-amber-300 flex items-center gap-2 border-b border-stone-800 pb-2">
            <span className="text-amber-500 font-mono text-sm">④</span> 미래의 귀결 및 주의점 <span className="text-xs text-stone-400 font-normal">({hasTransformation ? `지괘: ${transformedMeta.fullNameHangul}` : `본괘 유지`})</span>
          </h2>
          <div className="p-4 rounded-xl bg-stone-950/60 border border-stone-800/80 text-xs sm:text-sm text-stone-300 leading-relaxed">
            <div className="whitespace-pre-line text-stone-300 font-light">
              {section4Future}
            </div>
          </div>
        </div>

        {/* 💡 질문자에 대한 최종 종합 컨설팅 요약 */}
        <div className="p-5 rounded-2xl bg-gradient-to-r from-amber-950/40 via-stone-900 to-amber-950/30 border border-amber-500/50 shadow-xl space-y-2.5">
          <div className="flex items-center gap-2 text-sm font-bold text-amber-400">
            <Lightbulb className="w-5 h-5 text-amber-400 shrink-0" />
            <span>💡 질문자에 대한 최종 종합 컨설팅 요약</span>
          </div>
          <div className="text-xs sm:text-sm text-stone-100 font-medium leading-relaxed italic border-l-2 border-amber-400 pl-3.5 whitespace-pre-line">
            {section5Summary}
          </div>
        </div>

        {/* 하단 상담 진행 버튼 */}
        <div className="pt-4 border-t border-stone-800 flex flex-col sm:flex-row items-center justify-between gap-4">
          <span className="text-xs text-stone-400 font-light">
            종합 컨설팅 리포트를 숙고하신 후, 상담사와 심층 질의응답을 이어가세요.
          </span>

          <button
            onClick={onProceedToCounsel}
            className="w-full sm:w-auto px-7 py-3.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-stone-950 font-semibold text-sm transition-all shadow-lg shadow-amber-950/40 flex items-center justify-center gap-2 cursor-pointer active:scale-[0.98]"
          >
            <span>상담 진행하기</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    </motion.div>
  );
};
