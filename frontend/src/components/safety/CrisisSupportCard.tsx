'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { Phone, Heart, RotateCcw } from 'lucide-react';

export interface CrisisResourceItem {
  id: string;
  name: string;
  tel: string;
  hours: string;
  description?: string;
  online_url?: string;
}

interface CrisisSupportCardProps {
  onRestart?: () => void;
  resources?: CrisisResourceItem[];
  className?: string;
}

export const CrisisSupportCard: React.FC<CrisisSupportCardProps> = ({
  onRestart,
  resources,
  className = '',
}) => {
  const subHotlines = resources && resources.length > 0
    ? resources.filter((r) => r.tel !== '109')
    : [
        { id: '1577-0199', name: '정신건강 상담', tel: '1577-0199' },
        { id: '1388', name: '청소년 전화', tel: '1388' },
        { id: '1366', name: '여성긴급 전화', tel: '1366' },
      ];

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.4 }}
      className={`w-full max-w-xl mx-auto p-6 sm:p-8 rounded-2xl bg-stone-900/90 border border-stone-800 text-stone-200 shadow-2xl backdrop-blur-md ${className}`}
    >
      <div className="flex items-center gap-3 text-amber-500 mb-4">
        <Heart className="w-6 h-6 animate-pulse" />
        <span className="text-sm font-semibold tracking-wider">따뜻한 도움이 곁에 있습니다</span>
      </div>

      <h3 className="text-xl font-serif font-medium text-stone-100 mb-3 leading-snug">
        지금 남겨주신 마음의 무게를 그냥 지나칠 수 없었습니다.
      </h3>

      <p className="text-sm text-stone-300 font-light leading-relaxed mb-6">
        주역의 괘를 뽑는 것보다, 지금은 당신의 소중한 이야기를 안전하게 들어줄 수 있는 전문 상담사와 이야기를 나누는 것이 무엇보다 중요합니다.
      </p>

      {/* 긴급 지원 핫라인 목록 (단순 안내) */}
      <div className="space-y-3 mb-6">
        <div className="flex items-center justify-between p-4 rounded-xl bg-amber-500/10 border border-amber-500/30">
          <div>
            <div className="text-xs text-amber-400 font-medium">자살예방 및 위기상담전화</div>
            <div className="text-lg font-bold text-stone-100">국번없이 109</div>
          </div>
          <div className="flex items-center gap-1 text-xs text-amber-400 font-medium bg-amber-500/20 px-3 py-1.5 rounded-lg">
            <Phone className="w-3.5 h-3.5" />
            <span>24시간 무료</span>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs">
          {subHotlines.map((item) => (
            <div
              key={item.id || item.tel}
              className="p-3 rounded-lg bg-stone-800/60 border border-stone-700/60 flex justify-between items-center"
            >
              <div>
                <span className="text-stone-400 block text-[11px] truncate">{item.name}</span>
                <span className="font-semibold text-stone-200">{item.tel}</span>
              </div>
              <Phone className="w-3.5 h-3.5 text-stone-500 flex-shrink-0 ml-1" />
            </div>
          ))}
        </div>
      </div>

      <div className="pt-4 border-t border-stone-800 flex justify-between items-center text-xs text-stone-500">
        <span>* 본 서비스는 의학적·심리적 치료를 대체하지 않습니다.</span>
        {onRestart && (
          <button
            onClick={onRestart}
            className="flex items-center gap-1 text-stone-400 hover:text-stone-200 transition cursor-pointer"
          >
            <RotateCcw className="w-3 h-3" />
            <span>처음으로 돌아가기</span>
          </button>
        )}
      </div>
    </motion.div>
  );
};
