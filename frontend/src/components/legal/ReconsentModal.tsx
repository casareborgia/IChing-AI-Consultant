'use client';

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, ShieldAlert, Sparkles, AlertCircle, ArrowRight } from 'lucide-react';
import { LATEST_LEGAL_REVISION } from '@/lib/legalHistory';
import { useAuth } from '@/context/AuthContext';

interface ReconsentModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export const ReconsentModal: React.FC<ReconsentModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
}) => {
  const { recordConsent } = useAuth();
  const [ageConfirmed, setAgeConfirmed] = useState<boolean>(false);
  const [termsAgreed, setTermsAgreed] = useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleConfirm = async () => {
    if (!ageConfirmed || !termsAgreed || isSubmitting) return;

    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      const ok = await recordConsent();
      if (ok) {
        onSuccess();
        onClose();
      } else {
        setErrorMessage('동의 저장에 실패했습니다. 다시 시도해 주세요.');
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '동의 처리 중 오류가 발생했습니다.';
      setErrorMessage(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleClose = () => {
    if (isSubmitting) return;
    setErrorMessage(null);
    onClose();
  };

  const isButtonEnabled = ageConfirmed && termsAgreed && !isSubmitting;

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4">
        {/* Backdrop */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={handleClose}
          className="absolute inset-0 bg-stone-950/80 backdrop-blur-md"
        />

        {/* Modal Dialog */}
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 15 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 15 }}
          className="relative w-full max-w-lg overflow-hidden rounded-3xl border border-stone-800 bg-stone-900 shadow-2xl text-stone-200"
        >
          {/* Header */}
          <div className="flex items-center justify-between border-b border-stone-800/80 px-6 py-4 bg-stone-900/90">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400">
                <ShieldAlert className="w-4 h-4" />
              </div>
              <div>
                <h3 className="text-base font-bold text-stone-100 font-serif">
                  이용약관 및 개인정보처리방침 개정 안내
                </h3>
                <p className="text-[11px] text-stone-400 font-light">
                  서비스 정책 변경에 따라 재동의가 필요합니다.
                </p>
              </div>
            </div>
            <button
              onClick={handleClose}
              disabled={isSubmitting}
              className="p-1 rounded-lg text-stone-400 hover:text-stone-100 hover:bg-stone-800 transition cursor-pointer disabled:opacity-50"
              title="닫기"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Body */}
          <div className="p-6 space-y-4 max-h-[70vh] overflow-y-auto">
            {/* 변경 사항 안내 블록 */}
            <div className="space-y-2.5 rounded-2xl border border-amber-500/20 bg-amber-500/5 p-4 text-xs text-stone-300">
              <div className="flex items-center gap-1.5 text-amber-400 font-medium">
                <Sparkles className="w-4 h-4" />
                <span>주요 개정 내용 ({LATEST_LEGAL_REVISION.version})</span>
              </div>
              <p className="text-stone-200 font-medium leading-relaxed">
                {LATEST_LEGAL_REVISION.summary}
              </p>
              <ul className="list-disc pl-4 space-y-1 text-stone-400 leading-relaxed text-[11px]">
                {LATEST_LEGAL_REVISION.changes.map((change, idx) => (
                  <li key={idx}>{change}</li>
                ))}
              </ul>
            </div>

            {/* 체크박스 영역 */}
            <div className="space-y-3 rounded-2xl border border-stone-800/80 bg-stone-950/40 p-4 text-xs text-stone-300">
              <label className="flex items-start gap-2.5 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={ageConfirmed}
                  onChange={(e) => setAgeConfirmed(e.target.checked)}
                  disabled={isSubmitting}
                  className="mt-0.5 h-4 w-4 rounded border-stone-700 bg-stone-900 text-amber-500 focus:ring-amber-500 focus:ring-offset-0 cursor-pointer"
                />
                <span className="leading-tight">
                  <strong className="text-amber-400">[필수]</strong> 만 19세 이상입니다.
                </span>
              </label>

              <label className="flex items-start gap-2.5 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={termsAgreed}
                  onChange={(e) => setTermsAgreed(e.target.checked)}
                  disabled={isSubmitting}
                  className="mt-0.5 h-4 w-4 rounded border-stone-700 bg-stone-900 text-amber-500 focus:ring-amber-500 focus:ring-offset-0 cursor-pointer"
                />
                <span className="leading-tight">
                  <strong className="text-amber-400">[필수]</strong> 개정된{' '}
                  <a
                    href="/terms"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="underline underline-offset-2 hover:text-amber-300 transition"
                    onClick={(e) => e.stopPropagation()}
                  >
                    이용약관
                  </a>
                  {' '}및{' '}
                  <a
                    href="/privacy"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="underline underline-offset-2 hover:text-amber-300 transition"
                    onClick={(e) => e.stopPropagation()}
                  >
                    개인정보처리방침
                  </a>
                  에 모두 동의합니다.
                </span>
              </label>

              <p className="pt-1 text-[10px] leading-normal text-stone-500">
                ※ 본 확인은 만 19세 이상 확인용이며, 본인확인기관을 통한 법적 본인확인 절차가 아닙니다 (운영자 결정 D02).
              </p>
            </div>

            {/* 에러 메시지 (실패 시 모달 닫지 않고 노출) */}
            {errorMessage && (
              <div className="flex items-center gap-2 rounded-xl bg-red-950/40 border border-red-900/60 p-3 text-xs text-red-300">
                <AlertCircle className="w-4 h-4 shrink-0 text-red-400" />
                <span>{errorMessage}</span>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="flex items-center justify-end gap-2.5 border-t border-stone-800/80 px-6 py-4 bg-stone-900/90">
            <button
              onClick={handleClose}
              disabled={isSubmitting}
              className="px-4 py-2 rounded-xl text-xs text-stone-400 hover:text-stone-200 hover:bg-stone-800 transition cursor-pointer disabled:opacity-50"
            >
              닫기
            </button>
            <button
              onClick={handleConfirm}
              disabled={!isButtonEnabled}
              className={`flex items-center gap-1.5 px-5 py-2 rounded-xl text-xs font-semibold transition ${
                isButtonEnabled
                  ? 'bg-amber-400 hover:bg-amber-300 text-stone-900 shadow-md cursor-pointer'
                  : 'bg-stone-800 text-stone-500 cursor-not-allowed opacity-60'
              }`}
            >
              <span>{isSubmitting ? '동의 처리 중...' : '동의하고 계속하기'}</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
};
