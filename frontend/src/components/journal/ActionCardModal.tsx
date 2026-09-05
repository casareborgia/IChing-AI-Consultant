'use client';

import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Copy, Download, Sparkles, X } from 'lucide-react';

interface ActionCardModalProps {
  isOpen: boolean;
  imageUrl: string | null;
  isServerDownloading: boolean;
  copied: boolean;
  onClose: () => void;
  onDownloadLocal: () => void;
  onDownloadServer: () => void;
  onCopyImage: () => void;
}

export const ActionCardModal: React.FC<ActionCardModalProps> = ({
  isOpen,
  imageUrl,
  isServerDownloading,
  copied,
  onClose,
  onDownloadLocal,
  onDownloadServer,
  onCopyImage,
}) => {
  if (!isOpen || !imageUrl) return null;

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.95 }}
          transition={{ duration: 0.2 }}
          className="relative max-w-sm w-full bg-stone-900 border border-stone-700/80 rounded-2xl p-5 shadow-2xl flex flex-col max-h-[90vh]"
        >
          {/* 모달 헤더 */}
          <div className="flex items-center justify-between pb-3 border-b border-stone-800 mb-3">
            <div className="flex items-center gap-2 text-amber-400 font-medium text-sm">
              <Sparkles className="w-4 h-4" />
              <span>마음 전념 카드 이미지 소장</span>
            </div>
            <button
              onClick={onClose}
              className="p-1 rounded-lg hover:bg-stone-800 text-stone-400 hover:text-stone-200 cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* 안내 문구 */}
          <p className="text-xs text-stone-400 mb-3 text-center">
            기기에 파일이 자동 저장되었습니다. 자동 다운로드가 되지 않은 경우{' '}
            <strong className="text-amber-400">아래 이미지를 우클릭 또는 꾹 눌러 &apos;이미지 저장&apos;</strong>을 선택해 주세요.
          </p>

          {/* 고화질 카드 이미지 미리보기 */}
          <div className="overflow-y-auto flex-1 rounded-xl border border-stone-800/80 mb-4 bg-stone-950 flex justify-center p-2">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={imageUrl}
              alt="마음 전념 카드 고화질 이미지"
              className="w-full h-auto rounded-lg shadow-lg"
            />
          </div>

          {/* 모달 액션 버튼 */}
          <div className="flex gap-2">
            <button
              onClick={onDownloadLocal}
              className="flex-1 py-2.5 px-3 rounded-xl bg-amber-600 hover:bg-amber-500 text-stone-950 font-semibold text-xs flex items-center justify-center gap-1.5 cursor-pointer shadow-md"
            >
              <Download className="w-4 h-4" />
              <span>기기 저장</span>
            </button>
            <button
              onClick={onDownloadServer}
              disabled={isServerDownloading}
              className="py-2.5 px-3 rounded-xl bg-stone-800 hover:bg-stone-700 text-amber-400 hover:text-amber-300 text-xs flex items-center justify-center gap-1.5 cursor-pointer border border-stone-700 disabled:opacity-50"
              title="EXIF 메타데이터가 완전 제거된 고화질 원본 이미지"
            >
              <Sparkles className="w-4 h-4 text-amber-400" />
              <span>{isServerDownloading ? '렌더링 중...' : '서버 고화질'}</span>
            </button>
            <button
              onClick={onCopyImage}
              className="py-2.5 px-3 rounded-xl bg-stone-800 hover:bg-stone-700 text-stone-200 text-xs flex items-center justify-center gap-1.5 cursor-pointer border border-stone-700"
            >
              <Copy className="w-4 h-4" />
              <span>{copied ? '복사됨!' : '복사'}</span>
            </button>
            <button
              onClick={onClose}
              className="py-2.5 px-2.5 rounded-xl bg-stone-800 hover:bg-stone-700 text-stone-400 text-xs cursor-pointer border border-stone-700"
            >
              닫기
            </button>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
};
