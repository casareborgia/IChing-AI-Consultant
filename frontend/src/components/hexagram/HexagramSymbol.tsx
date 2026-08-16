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
  const heightClass = size === 'sm' ? 'h-1.5' : size === 'lg' ? 'h-3.5' : 'h-2.5';
  const gapClass = size === 'sm' ? 'gap-1' : size === 'lg' ? 'gap-2' : 'gap-1.5';
  const widthClass = size === 'sm' ? 'w-16' : size === 'lg' ? 'w-36' : 'w-24';
  const roundedClass = size === 'sm' ? 'rounded-[2px]' : 'rounded-[3px]';

  return (
    <div className={`inline-flex flex-col ${gapClass} ${widthClass} ${className}`}>
      {displayLines.map((line, idx) => {
        // 애니메이션 딜레이: 초효(아래)부터 위로 그려지도록 역순 인덱스 기반 계산
        const drawOrder = line.position - 1; // 0 ~ 5 (아래부터 위로)
        const delay = animated ? drawOrder * 0.15 : 0;

        const isYang = line.isYang;
        const isChanging = line.isChanging;

        // 색상 스타일
        // 양/음 기본: 차분한 먹색/그레이, 동효: 따뜻한 앰버/골드
        const barBaseColor = isChanging
          ? 'bg-amber-600 dark:bg-amber-400 shadow-[0_0_8px_rgba(217,119,6,0.5)]'
          : 'bg-zinc-700 dark:bg-zinc-300';

        return (
          <motion.div
            key={`line-${line.position}`}
            initial={animated ? { opacity: 0, scaleX: 0.2, y: 10 } : { opacity: 1 }}
            animate={{ opacity: 1, scaleX: 1, y: 0 }}
            transition={{ duration: 0.4, delay, ease: [0.22, 1, 0.36, 1] }}
            className="flex items-center justify-between relative group"
          >
            {showPositions && (
              <span className="absolute -left-6 text-[10px] text-zinc-400 font-serif">
                {line.position === 1 ? '初' : line.position === 6 ? '上' : line.position}
              </span>
            )}

            {isYang ? (
              // 양효: 하나의 이어진 선
              <div className={`w-full ${heightClass} ${barBaseColor} ${roundedClass} transition-colors`} />
            ) : (
              // 음효: 가운데가 끊긴 두 개의 선
              <div className="w-full flex justify-between">
                <div className={`w-[44%] ${heightClass} ${barBaseColor} ${roundedClass} transition-colors`} />
                <div className={`w-[44%] ${heightClass} ${barBaseColor} ${roundedClass} transition-colors`} />
              </div>
            )}

            {/* 동효(변효) 강조 표식 */}
            {isChanging && (
              <motion.span
                initial={{ scale: 0 }}
                animate={{ scale: [1, 1.25, 1] }}
                transition={{ repeat: Infinity, duration: 2, delay: delay + 0.3 }}
                className="absolute -right-4 w-2 h-2 rounded-full bg-amber-500 shadow-[0_0_6px_rgba(245,158,11,0.8)]"
                title={`제${line.position}효 변효(${line.value === 9 ? '노양' : '노음'})`}
              />
            )}
          </motion.div>
        );
      })}
    </div>
  );
};
