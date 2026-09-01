'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { ArrowRight, Sparkles, Compass } from 'lucide-react';
import { CastResult } from '../../types/iching';
import { HEXAGRAMS_META } from '../../data/hexagramsData';
import { HexagramSymbol } from './HexagramSymbol';

interface HexagramCardProps {
  castResult: CastResult;
  animated?: boolean;
  onProceedToCounsel?: () => void;
  className?: string;
}

export const HexagramCard: React.FC<HexagramCardProps> = ({
  castResult,
  animated = true,
  onProceedToCounsel,
  className = '',
}) => {
  const originalMeta = HEXAGRAMS_META[castResult.originalHexId];
  const transformedMeta = HEXAGRAMS_META[castResult.transformedHexId];
  const hasTransformation = castResult.changingPositions.length > 0;

  // 지괘(변화 후 괘)의 효 라인 생성
  const transformedLines = castResult.lines.map((l) => {
    if (l.value === 6) {
      return { ...l, isYang: true, isChanging: false, value: 7 as const };
    }
    if (l.value === 9) {
      return { ...l, isYang: false, isChanging: false, value: 8 as const };
    }
    return { ...l, isChanging: false };
  });

  return (
    <motion.div
      initial={animated ? { opacity: 0, y: 20 } : { opacity: 1 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: 'easeOut' }}
      className={`w-full max-w-2xl mx-auto bg-stone-900/60 dark:bg-stone-900/80 backdrop-blur-md border border-stone-800/80 rounded-2xl p-6 sm:p-8 shadow-xl text-stone-100 ${className}`}
    >
      {/* 상단 뱃지 */}
      <div className="flex items-center justify-between border-b border-stone-800/80 pb-4 mb-6">
        <div className="flex items-center gap-2 text-xs uppercase tracking-widest text-amber-500/90 font-medium">
          <Compass className="w-4 h-4" />
          <span>도출된 주역의 괘상 (卦象)</span>
        </div>
        {hasTransformation ? (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <Sparkles className="w-3 h-3" />
            동효 {castResult.changingPositions.length}개 변화
          </span>
        ) : (
          <span className="px-2.5 py-1 rounded-full text-xs font-medium bg-stone-800 text-stone-400 border border-stone-700">
            변효 없음 (본괘 중심)
          </span>
        )}
      </div>

      {/* 괘 그래픽 및 정보 영역 (본괘 / 지괘) */}
      <div className={`grid ${hasTransformation ? 'grid-cols-1 md:grid-cols-[1fr,auto,1fr]' : 'grid-cols-1'} items-center gap-6 my-4`}>
        {/* 1. 본괘 (현재의 흐름과 상황) */}
        <div className="flex flex-col items-center text-center p-5 rounded-xl bg-stone-950/40 border border-stone-800/50">
          <span className="text-xs text-stone-400 mb-2 font-medium tracking-wide">
            [본괘] 현재 마주한 상황
          </span>

          <div className="my-4">
            <HexagramSymbol lines={castResult.lines} size="lg" animated={animated} showPositions />
          </div>

          <div className="mt-3">
            <div className="flex items-center justify-center gap-2">
              <span className="text-2xl font-serif font-semibold text-stone-100">
                {originalMeta.fullNameHangul}
              </span>
              <span className="text-sm font-serif text-amber-500/80 px-1.5 py-0.5 rounded bg-amber-500/10 border border-amber-500/20">
                {originalMeta.nameHanja}
              </span>
            </div>
            <p className="text-xs text-stone-400 mt-1">
              상괘 {originalMeta.upperTrigram} · 하괘 {originalMeta.lowerTrigram}
            </p>
          </div>

          <div className="mt-4 pt-3 border-t border-stone-800/60 w-full">
            <p className="text-xs text-stone-300 font-light leading-relaxed">
              &ldquo;{originalMeta.natureSummary}&rdquo;
            </p>
          </div>
        </div>

        {/* 변화 화살표 (동효가 있을 때만 표시) */}
        {hasTransformation && (
          <div className="flex flex-col items-center justify-center text-stone-500">
            <div className="hidden md:flex flex-col items-center gap-1">
              <span className="text-[10px] text-amber-400/90 font-serif">변화</span>
              <ArrowRight className="w-5 h-5 text-amber-500 animate-pulse" />
            </div>
            <div className="flex md:hidden items-center gap-2 py-1">
              <span className="text-xs text-amber-400">지혜의 흐름으로 나아감</span>
              <ArrowRight className="w-4 h-4 text-amber-500" />
            </div>
          </div>
        )}

        {/* 2. 지괘 (변화 후 나아갈 방향 - 동효가 있을 때) */}
        {hasTransformation && (
          <div className="flex flex-col items-center text-center p-5 rounded-xl bg-stone-950/40 border border-stone-800/50">
            <span className="text-xs text-stone-400 mb-2 font-medium tracking-wide">
              [지괘] 변화해 나아갈 흐름
            </span>

            <div className="my-4">
              <HexagramSymbol lines={transformedLines} size="lg" animated={false} />
            </div>

            <div className="mt-3">
              <div className="flex items-center justify-center gap-2">
                <span className="text-2xl font-serif font-semibold text-stone-100">
                  {transformedMeta.fullNameHangul}
                </span>
                <span className="text-sm font-serif text-stone-400 px-1.5 py-0.5 rounded bg-stone-800 border border-stone-700">
                  {transformedMeta.nameHanja}
                </span>
              </div>
              <p className="text-xs text-stone-400 mt-1">
                상괘 {transformedMeta.upperTrigram} · 하괘 {transformedMeta.lowerTrigram}
              </p>
            </div>

            <div className="mt-4 pt-3 border-t border-stone-800/60 w-full">
              <p className="text-xs text-stone-300 font-light leading-relaxed">
                &ldquo;{transformedMeta.natureSummary}&rdquo;
              </p>
            </div>
          </div>
        )}
      </div>

      {/* 핵심 의미 가이드 영역 */}
      <div className="mt-6 space-y-3">
        {/* 고변점 해석 초점 */}
        {castResult.focusRule?.descriptionKo && (
          <div className="p-3.5 rounded-xl bg-stone-950/60 border border-stone-800/80 text-stone-300">
            <div className="text-xs font-medium text-stone-400 flex items-center gap-1.5 mb-1">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-400"></span>
              <span>해석 초점 (주자 고변점)</span>
            </div>
            <p className="text-xs sm:text-sm text-stone-200 leading-relaxed">
              {castResult.focusRule.descriptionKo}
            </p>
          </div>
        )}

        {/* 체용(體用) 보완 규칙 안내 */}
        {castResult.focusRule?.bodyUseNoteKo && (
          <div className="p-3.5 rounded-xl bg-amber-950/20 border border-amber-500/30 text-amber-200/90">
            <div className="text-xs font-semibold text-amber-400 flex items-center gap-1.5 mb-1">
              <span>⚖️ 체용(體用) 보완 지침</span>
            </div>
            <p className="text-xs sm:text-sm leading-relaxed">
              {castResult.focusRule.bodyUseNoteKo}
            </p>
          </div>
        )}

        {/* 괘의 성격 — 사실 서술만 둔다.
            예전에는 "…의 태도로 유연하게 전환해 나가는 지혜가 권장됩니다"를 붙였는데,
            조건이 지괘 유무 하나뿐이라 동효가 있으면 무조건 전환을 권했다. 체용이
            본괘 위주를 가리키는 288개 조합에서는 위 지침과 정반대 권고였다.
            게다가 이 문장은 정적 표(hexagramsData)에서 조립된다 — 괘사도 초점 규칙도
            거치지 않은 권고다. 권고는 근거를 갖춘 상담 답변에서만 나가야 한다.
            그래서 이 블록은 괘의 성격과 흐름만 말하고, 어느 쪽에 무게를 둘지는
            위 초점·체용 블록이, 무엇을 할지는 상담이 말한다. */}
        <div className="p-4 rounded-xl bg-amber-500/5 border border-amber-500/20 text-stone-300">
          <div className="text-xs font-semibold text-amber-400 flex items-center gap-1.5 mb-1.5">
            <span>💡 이 괘의 성격</span>
          </div>
          <p className="text-sm font-normal leading-relaxed text-stone-200">
            {hasTransformation
              ? `${originalMeta.coreTheme}의 자리에서 ${transformedMeta.coreTheme}의 성격으로 옮겨 가는 흐름입니다.`
              : `${originalMeta.coreTheme}의 자리입니다.`}
          </p>
        </div>
      </div>

      {/* 괘 해석 리포트 확인 버튼 (옵션) */}
      {onProceedToCounsel && (
        <div className="mt-6 flex justify-end">
          <button
            onClick={onProceedToCounsel}
            className="w-full sm:w-auto px-6 py-3 rounded-xl bg-amber-500 hover:bg-amber-400 text-stone-950 font-medium text-sm transition-all shadow-lg shadow-amber-950/40 hover:shadow-amber-500/20 flex items-center justify-center gap-2 cursor-pointer"
          >
            <span>괘 해석 리포트 확인하기</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      )}
    </motion.div>
  );
};
