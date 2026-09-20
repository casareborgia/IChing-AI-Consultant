'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { ShieldAlert, ArrowRight } from 'lucide-react';
import { getReportErrorMessage } from '../../lib/api';

interface HexagramReportFailureViewProps {
  errorCode?: string | null;
  onProceedToCounsel: () => void;
}

export const HexagramReportFailureView: React.FC<HexagramReportFailureViewProps> = ({
  errorCode,
  onProceedToCounsel,
}) => {
  const message = getReportErrorMessage(errorCode);

  return (
    <div className="w-full max-w-3xl mx-auto py-8">
      <motion.div
        initial={{ opacity: 0, y: 15 }}
        animate={{ opacity: 1, y: 0 }}
        className="rounded-3xl border border-amber-500/30 bg-stone-900/95 p-8 text-stone-100 shadow-2xl space-y-6"
      >
        <div className="flex items-center gap-3 text-amber-400">
          <ShieldAlert className="w-6 h-6 shrink-0" />
          <h2 className="text-lg font-serif font-bold">맞춤 분석 리포트를 준비하지 못했습니다</h2>
        </div>

        <p className="text-sm sm:text-base leading-relaxed text-stone-300">
          {message}
        </p>

        <div className="rounded-2xl border border-stone-800 bg-stone-950/60 p-4 text-xs text-stone-400 space-y-1">
          <p>
            • 괘 도출 결과와 상담 대화 엔진은 정상 동작 중입니다.
          </p>
          <p>
            • 아래 버튼을 누르시면 기다림 없이 AI 상담사와 곧바로 대화를 시작하실 수 있습니다.
          </p>
        </div>

        <div className="pt-2">
          <button
            onClick={onProceedToCounsel}
            className="inline-flex items-center gap-2 rounded-2xl bg-amber-500 px-6 py-3.5 text-sm font-bold text-stone-950 hover:bg-amber-400 transition shadow-lg shadow-amber-500/10"
          >
            <span>상담 대화로 계속하기</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </motion.div>
    </div>
  );
};
