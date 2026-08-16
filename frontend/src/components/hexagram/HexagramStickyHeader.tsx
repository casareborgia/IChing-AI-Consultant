'use client';

import React, { useState } from 'react';
import { ChevronDown, ChevronUp, Sparkles, X } from 'lucide-react';
import { CastResult } from '../../types/iching';
import { HEXAGRAMS_META } from '../../data/hexagramsData';
import { HexagramSymbol } from './HexagramSymbol';
import { HexagramCard } from './HexagramCard';

interface HexagramStickyHeaderProps {
  castResult: CastResult;
  userQuestion?: string;
}

export const HexagramStickyHeader: React.FC<HexagramStickyHeaderProps> = ({ castResult, userQuestion }) => {
  const [isOpen, setIsOpen] = useState(false);
  const originalMeta = HEXAGRAMS_META[castResult.originalHexId];
  const transformedMeta = HEXAGRAMS_META[castResult.transformedHexId];
  const hasTransformation = castResult.changingPositions.length > 0;

  return (
    <>
      {/* 상단 고정 미니 바 */}
      <div className="sticky top-0 z-30 w-full bg-stone-950/85 backdrop-blur-md border-b border-stone-800/80 px-4 py-2.5 transition-all">
        <div className="max-w-3xl mx-auto flex items-center justify-between gap-2">
          {/* 좌측: 괘 미니 심볼 & 이름 & 질문 */}
          <div className="flex items-center gap-3 min-w-0">
            <div className="p-1 rounded bg-stone-900 border border-stone-800 shrink-0">
              <HexagramSymbol lines={castResult.lines} size="sm" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-1.5 flex-wrap">
                <span className="text-sm font-serif font-medium text-stone-200">
                  {originalMeta.fullNameHangul} ({originalMeta.nameHanja})
                </span>
                {hasTransformation && (
                  <span className="text-xs text-stone-400 flex items-center gap-1">
                    ➔ {transformedMeta.fullNameHangul}
                  </span>
                )}
              </div>
              <p className="text-[11px] text-stone-400 font-light truncate max-w-xs sm:max-w-md">
                {userQuestion ? `물음: "${userQuestion}"` : originalMeta.coreTheme}
              </p>
            </div>
          </div>

          {/* 우측: 상세 보기 토글 버튼 */}
          <button
            onClick={() => setIsOpen(!isOpen)}
            className="flex items-center gap-1 text-xs font-medium text-amber-500/90 hover:text-amber-400 px-2.5 py-1.5 rounded-lg bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/20 transition-all cursor-pointer"
          >
            <span>{isOpen ? '닫기' : '괘상 상세보기'}</span>
            {isOpen ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </button>
        </div>
      </div>

      {/* 펼침 모달/드로어 */}
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="relative w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <button
              onClick={() => setIsOpen(false)}
              className="absolute top-4 right-4 z-10 p-2 rounded-full bg-stone-800/80 text-stone-300 hover:text-white hover:bg-stone-700 transition cursor-pointer"
            >
              <X className="w-4 h-4" />
            </button>
            <HexagramCard castResult={castResult} animated={false} />
          </div>
        </div>
      )}
    </>
  );
};
