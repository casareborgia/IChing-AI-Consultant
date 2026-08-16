'use client';

import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { BookOpen, ChevronDown, ChevronUp, HelpCircle, AlertCircle } from 'lucide-react';
import { ChatMessage as ChatMessageType } from '../../types/iching';

interface ChatMessageProps {
  message: ChatMessageType;
}

export const ChatMessage: React.FC<ChatMessageProps> = ({ message }) => {
  const [showEvidences, setShowEvidences] = useState(false);
  const isUser = message.sender === 'user';
  const isSystem = message.sender === 'system';

  if (isSystem) {
    return (
      <div className="flex justify-center my-4">
        <span className="text-xs text-stone-400 bg-stone-900/80 px-3 py-1.5 rounded-full border border-stone-800">
          {message.content}
        </span>
      </div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className={`flex flex-col mb-6 ${isUser ? 'items-end' : 'items-start'}`}
    >
      <div className="flex items-center gap-2 mb-1 px-1">
        <span className="text-[11px] font-medium text-stone-500">
          {isUser ? '나의 이야기' : '주역 상담사'}
        </span>
        <span className="text-[10px] text-stone-600">{message.timestamp}</span>
      </div>

      <div
        className={`relative max-w-[88%] sm:max-w-xl rounded-2xl p-4 sm:p-5 text-sm leading-relaxed ${
          isUser
            ? 'bg-amber-600/90 text-stone-950 rounded-tr-sm font-medium shadow-md shadow-amber-950/20'
            : 'bg-stone-900/90 text-stone-200 border border-stone-800/80 rounded-tl-sm shadow-md'
        }`}
      >
        {/* 재삼독(중복 질문) 알림 */}
        {message.isDuplicateAlert && (
          <div className="flex items-center gap-1.5 text-xs text-amber-400 mb-2 p-2 rounded-lg bg-amber-500/10 border border-amber-500/20">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>이전에도 비슷한 물음을 주셨습니다. 괘를 다시 뽑기보다 지난 대화 이후의 변화를 살펴봅니다.</span>
          </div>
        )}

        {/* 본문 텍스트 */}
        <p className="whitespace-pre-wrap">{message.content}</p>

        {/* 상담사의 되묻기 질문 (질문 강조) */}
        {message.followupQuestion && (
          <div className="mt-3 pt-3 border-t border-stone-800/80">
            <div className="flex items-start gap-2 p-3 rounded-xl bg-amber-500/5 border border-amber-500/20 text-stone-200">
              <HelpCircle className="w-4 h-4 text-amber-500 shrink-0 mt-0.5" />
              <div>
                <span className="text-[11px] font-semibold text-amber-400 block mb-0.5">
                  함께 짚어볼 질문
                </span>
                <span className="text-xs sm:text-sm font-medium text-stone-100">
                  {message.followupQuestion}
                </span>
              </div>
            </div>
          </div>
        )}

        {/* 주석 원문 근거 (정전 / 본의) 아코디언 */}
        {message.evidences && message.evidences.length > 0 && (
          <div className="mt-3 pt-2 border-t border-stone-800/60">
            <button
              onClick={() => setShowEvidences(!showEvidences)}
              className="flex items-center justify-between w-full py-1 text-xs text-stone-400 hover:text-amber-400 transition cursor-pointer"
            >
              <div className="flex items-center gap-1.5">
                <BookOpen className="w-3.5 h-3.5" />
                <span>해석의 고전 근거 ({message.evidences.length}건)</span>
              </div>
              {showEvidences ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            </button>

            {showEvidences && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                className="mt-2 space-y-2 text-xs text-stone-400"
              >
                {message.evidences.map((ev, idx) => (
                  <div key={idx} className="p-2.5 rounded-lg bg-stone-950/60 border border-stone-800/60">
                    <div className="text-[10px] text-amber-500/90 font-medium mb-1">
                      {ev.sourceTitle}
                    </div>
                    <p className="text-stone-300 text-[11px] font-light leading-relaxed">
                      {ev.content}
                    </p>
                  </div>
                ))}
              </motion.div>
            )}
          </div>
        )}
      </div>
    </motion.div>
  );
};
