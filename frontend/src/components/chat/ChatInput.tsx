'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Send, Sparkles } from 'lucide-react';

interface ChatInputProps {
  onSendMessage: (message: string) => void;
  isLoading: boolean;
  placeholder?: string;
  className?: string;
}

export const ChatInput: React.FC<ChatInputProps> = ({
  onSendMessage,
  isLoading,
  placeholder = '마음속 생각을 편안하게 적어주세요...',
  className = '',
}) => {
  const [input, setInput] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // 자동 높이 조절
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`;
    }
  }, [input]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;
    onSendMessage(input.trim());
    setInput('');
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // 한글(IME) 조합 중 엔터 입력 시 중복 전송 및 글자 잘림 방지
    if (e.nativeEvent.isComposing) return;

    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className={`relative flex items-end gap-2 bg-stone-900/90 border border-stone-800 focus-within:border-amber-500/50 rounded-2xl p-2 sm:p-3 shadow-xl backdrop-blur-md transition-all ${className}`}
    >
      <textarea
        ref={textareaRef}
        rows={1}
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={isLoading}
        className="w-full resize-none bg-transparent text-sm text-stone-100 placeholder-stone-500 focus:outline-none px-2 py-1 max-h-32 disabled:opacity-50"
      />

      <button
        type="submit"
        disabled={!input.trim() || isLoading}
        className="p-2.5 rounded-xl bg-amber-600 hover:bg-amber-500 disabled:bg-stone-800 text-stone-950 disabled:text-stone-600 transition-all cursor-pointer disabled:cursor-not-allowed shrink-0"
      >
        <Send className="w-4 h-4" />
      </button>
    </form>
  );
};
