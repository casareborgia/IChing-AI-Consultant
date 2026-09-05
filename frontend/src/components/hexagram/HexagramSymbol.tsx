'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { LineInfo } from '../../types/iching';

interface HexagramSymbolProps {
  lines: LineInfo[]; // position 1(초효) ~ 6(상효)
  size?: 'sm' | 'md' | 'lg';
  animated?: boolean;
  className?: string;
  showPositions?: boolean;
}

export const HexagramSymbol: React.FC<HexagramSymbolProps> = ({
  lines,
  size = 'md',
  animated = false,
  className = '',
  showPositions = false,
}) => {
  // 화면에는 상효(position 6)가 맨 위, 초효(position 1)가 맨 아래로 보이도록 역순 렌더링
  const displayLines = [...lines].reverse();

  // 크기별 스타일 정의
  const heightClass = size === 'sm' ? 'h-2' : size === 'lg' ? 'h-3.5' : 'h-2.5';
  const gapClass = size === 'sm' ? 'gap-1.5' : size === 'lg' ? 'gap-2.5' : 'gap-2';
  const widthClass = size === 'sm' ? 'w-20' : size === 'lg' ? 'w-36' : 'w-28';
  const roundedClass = size === 'sm' ? 'rounded-[2px]' : 'rounded-[3px]';

  return (
    <div className={`inline-flex flex-col ${gapClass} ${widthClass} ${className} shrink-0`}>
      {displayLines.map((line) => {
        // 애니메이션 딜레이: 초효(아래)부터 위로 그려지도록 역순 인덱스 기반 계산
        const drawOrder = line.position - 1; // 0 ~ 5 (아래부터 위로)
        const delay = animated ? drawOrder * 0.12 : 0;

        const isYang = line.isYang;
        const isChanging = line.isChanging;

        // 색상 및 인라인 변효 하이라이트 스타일
        // 변효: 황금빛 네온 앰버 그라데이션 + 펄스 글로우
        const barBaseColor = isChanging
          ? 'bg-gradient-to-r from-amber-500 via-amber-400 to-amber-500 shadow-[0_0_10px_rgba(245,158,11,0.6)] border border-amber-300/80'
          : 'bg-stone-700 dark:bg-stone-400';

        return (
          <motion.div
            key={`line-${line.position}`}
            initial={animated ? { opacity: 0, scaleX: 0.2, y: 8 } : { opacity: 1 }}
            animate={{ opacity: 1, scaleX: 1, y: 0 }}
            transition={{ duration: 0.4, delay, ease: [0.22, 1, 0.36, 1] }}
            className="flex items-center justify-between relative group"
          >
            {showPositions && (
              <span className="absolute -left-6 text-[10px] text-stone-400 font-serif">
                {line.position === 1 ? '初' : line.position === 6 ? '上' : line.position}
              </span>
            )}

            {/* 효 막대 그래픽 */}
            {isYang ? (
              // 양효: 하나의 이어진 선
              <div className={`w-full ${heightClass} ${barBaseColor} ${roundedClass} transition-colors relative flex items-center justify-end px-1`}>
                {isChanging && (
                  <span className="text-[9px] font-bold text-stone-950 leading-none select-none font-mono">
                    ○
                  </span>
                )}
              </div>
            ) : (
              // 음효: 가운데가 끊긴 두 개의 선
              <div className="w-full flex justify-between relative">
                <div className={`w-[45%] ${heightClass} ${barBaseColor} ${roundedClass} transition-colors`} />
                <div className={`w-[45%] ${heightClass} ${barBaseColor} ${roundedClass} transition-colors relative flex items-center justify-end pr-0.5`}>
                  {isChanging && (
                    <span className="text-[9px] font-bold text-stone-950 leading-none select-none font-mono">
                      ✕
                    </span>
                  )}
                </div>
              </div>
            )}
          </motion.div>
        );
      })}
    </div>
  );
};
