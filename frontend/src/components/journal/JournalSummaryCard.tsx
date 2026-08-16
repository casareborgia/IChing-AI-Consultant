'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { BookmarkCheck, Calendar, CheckCircle2, RotateCcw, Share2 } from 'lucide-react';
import { JournalSummary } from '../../types/iching';

interface JournalSummaryCardProps {
  journal: JournalSummary;
  onRestart: () => void;
  className?: string;
}

export const JournalSummaryCard: React.FC<JournalSummaryCardProps> = ({
  journal,
  onRestart,
  className = '',
}) => {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.5 }}
      className={`w-full max-w-xl mx-auto p-6 sm:p-8 rounded-2xl bg-stone-900/90 border border-stone-800 text-stone-200 shadow-2xl backdrop-blur-md ${className}`}
    >
      <div className="flex items-center justify-between border-b border-stone-800 pb-4 mb-6">
        <div className="flex items-center gap-2 text-amber-500 font-serif">
          <BookmarkCheck className="w-5 h-5" />
          <span className="text-base font-semibold">오늘의 상담 저널 요약</span>
        </div>
        <div className="flex items-center gap-1.5 text-xs text-stone-500">
          <Calendar className="w-3.5 h-3.5" />
          <span>{journal.createdAt}</span>
        </div>
      </div>

      {/* 1. 명확해진 고민 */}
      <div className="mb-5">
        <span className="text-xs text-stone-400 font-medium block mb-1">정리된 물음</span>
        <p className="text-sm font-serif font-medium text-stone-100 p-3 rounded-xl bg-stone-950/50 border border-stone-800/80">
          &ldquo;{journal.clarifiedQuestion}&rdquo;
        </p>
      </div>

      {/* 2. 괘의 핵심 메시지 */}
      <div className="mb-5">
        <span className="text-xs text-stone-400 font-medium block mb-1">괘의 지혜</span>
        <p className="text-sm text-amber-200/90 leading-relaxed p-3 rounded-xl bg-amber-500/5 border border-amber-500/20">
          {journal.hexagramSummary}
        </p>
      </div>

      {/* 3. 주요 성찰 인사이트 */}
      <div className="mb-5">
        <span className="text-xs text-stone-400 font-medium block mb-2">되짚어볼 통찰</span>
        <div className="space-y-2">
          {journal.keyInsights.map((insight, idx) => (
            <div key={idx} className="flex items-start gap-2 text-xs text-stone-300">
              <CheckCircle2 className="w-4 h-4 text-amber-500 shrink-0 mt-0.5" />
              <span className="leading-relaxed">{insight}</span>
            </div>
          ))}
        </div>
      </div>

      {/* 4. 권장 행동 제안 */}
      <div className="mb-8 p-4 rounded-xl bg-stone-950/60 border border-stone-800 text-xs">
        <span className="text-amber-400 font-semibold block mb-1">실천해 볼 첫걸음</span>
        <p className="text-stone-300 leading-relaxed">{journal.suggestedAction}</p>
      </div>

      {/* 액션 버튼 */}
      <div className="flex flex-col sm:flex-row gap-3">
        <button
          onClick={onRestart}
          className="flex-1 py-3 px-4 rounded-xl bg-amber-600 hover:bg-amber-500 text-stone-950 font-medium text-xs transition flex items-center justify-center gap-1.5 cursor-pointer shadow-lg shadow-amber-950/40"
        >
          <RotateCcw className="w-4 h-4" />
          <span>새로운 상담 시작하기</span>
        </button>
      </div>
    </motion.div>
  );
};
