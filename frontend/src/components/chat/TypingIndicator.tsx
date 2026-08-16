'use client';

import React from 'react';
import { motion } from 'framer-motion';

interface TypingIndicatorProps {
  statusText?: string;
}

export const TypingIndicator: React.FC<TypingIndicatorProps> = ({
  statusText = '괘의 흐름과 생각을 가다듬고 있습니다...',
}) => {
  return (
    <div className="flex items-center gap-3 p-4 max-w-sm rounded-2xl bg-stone-900/80 border border-stone-800/80 text-stone-400 mb-6">
      <div className="flex items-center gap-1">
        {[0, 1, 2].map((i) => (
          <motion.span
            key={i}
            animate={{
              scale: [1, 1.3, 1],
              opacity: [0.4, 1, 0.4],
            }}
            transition={{
              duration: 1.2,
              repeat: Infinity,
              delay: i * 0.2,
              ease: 'easeInOut',
            }}
            className="w-1.5 h-1.5 rounded-full bg-amber-500"
          />
        ))}
      </div>
      <span className="text-xs font-light tracking-wide text-stone-300">
        {statusText}
      </span>
    </div>
  );
};
