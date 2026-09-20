'use client';

import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Sparkles, ShieldCheck, HeartHandshake } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';


interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const AuthModal: React.FC<AuthModalProps> = ({ isOpen, onClose }) => {
  const { signInWithGoogle } = useAuth();
  const [ageConfirmed, setAgeConfirmed] = React.useState(false);
  const [termsAgreed, setTermsAgreed] = React.useState(false);

  const handleGoogleLogin = async () => {
    // 우회 차단 (A21): DevTools 등으로 disabled 속성을 지우고 클릭하는 경우 방지
    if (!ageConfirmed || !termsAgreed) {
      return;
    }
    await signInWithGoogle();
  };

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        {/* Backdrop */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
          className="absolute inset-0 bg-stone-950/80 backdrop-blur-md"
        />

        {/* Modal Window */}
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 20 }}
          transition={{ type: 'spring', duration: 0.5, bounce: 0.2 }}
          className="relative w-full max-w-md overflow-hidden rounded-3xl border border-stone-800/80 bg-gradient-to-b from-stone-900 via-stone-900 to-stone-950 p-8 shadow-2xl shadow-stone-950/90 text-stone-200"
        >
          {/* Decorative ambient light */}
          <div className="pointer-events-none absolute -right-20 -top-20 h-44 w-44 rounded-full bg-amber-500/10 blur-3xl" />
          <div className="pointer-events-none absolute -bottom-20 -left-20 h-44 w-44 rounded-full bg-emerald-500/10 blur-3xl" />

          {/* Close button */}
          <button
            onClick={onClose}
            className="absolute right-5 top-5 rounded-full p-2 text-stone-400 transition hover:bg-stone-800 hover:text-stone-100"
            aria-label="닫기"
          >
            <X className="h-5 w-5" />
          </button>

          {/* Modal Header */}
          <div className="text-center">
            <div className="inline-flex h-14 w-14 items-center justify-center rounded-2xl border border-amber-500/30 bg-amber-500/10 text-2xl shadow-inner shadow-amber-500/20">
              ䷀
            </div>
            <h3 className="mt-4 font-serif text-2xl font-semibold tracking-tight text-stone-100">
              시작하기 (로그인 / 간편가입)
            </h3>
            <p className="mt-2 text-sm text-stone-400">
              처음 오셨다면 구글 계정으로 3초 간편가입 즉시 <span className="font-semibold text-amber-400">50 웰컴 크레딧</span>이 자동 지급됩니다.
            </p>
          </div>

          {/* 혜택 안내 배지 */}
          <div className="mt-6 space-y-2.5 rounded-2xl border border-stone-800/90 bg-stone-950/60 p-4 text-xs text-stone-300">
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-amber-400 shrink-0" />
              <span>가입 즉시 <strong>50 웰컴 크레딧</strong> 자동 지급 (대화 5회분 · 1회 10C)</span>
            </div>
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-emerald-400 shrink-0" />
              <span>상담 대화록 및 성찰 저널 자동 동기화 & 영구 보관</span>
            </div>
            <div className="flex items-center gap-2">
              <HeartHandshake className="h-4 w-4 text-amber-400 shrink-0" />
              <span>위기 감지 시 크레딧 미차감 안심 환불 보장</span>
            </div>
          </div>

          {/* 법적 필수 동의 및 연령 확인 체크박스 (AG-1 / A19, A21, A22, A24) */}
          <div className="mt-6 space-y-3 rounded-2xl border border-stone-800/80 bg-stone-950/40 p-4 text-xs text-stone-300">
            <label className="flex items-start gap-2.5 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={ageConfirmed}
                onChange={(e) => setAgeConfirmed(e.target.checked)}
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
                className="mt-0.5 h-4 w-4 rounded border-stone-700 bg-stone-900 text-amber-500 focus:ring-amber-500 focus:ring-offset-0 cursor-pointer"
              />
              <span className="leading-tight">
                <strong className="text-amber-400">[필수]</strong>{' '}
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
                에 동의합니다.
              </span>
            </label>

            <p className="pt-1 text-[10px] leading-normal text-stone-500">
              ※ 본 확인은 만 19세 이상 확인용이며, 본인확인기관을 통한 법적 본인확인 절차가 아닙니다 (운영자 결정 D02).
            </p>
          </div>

          {/* Social Login Buttons */}
          <div className="mt-5">
            {/* 구글 로그인 버튼 */}
            <button
              onClick={handleGoogleLogin}
              disabled={!(ageConfirmed && termsAgreed)}
              className={`flex w-full items-center justify-center gap-3 rounded-2xl border px-5 py-3.5 text-sm font-semibold shadow-md transition ${
                ageConfirmed && termsAgreed
                  ? 'border-stone-700 bg-stone-800/80 text-stone-100 hover:bg-stone-800 hover:border-stone-600 active:scale-[0.98] cursor-pointer'
                  : 'border-stone-800 bg-stone-900/50 text-stone-500 cursor-not-allowed opacity-60'
              }`}
            >
              <svg className="h-5 w-5" viewBox="0 0 24 24">
                <path fill="#EA4335" d="M12 5c1.6 0 3 .6 4.1 1.7l3.1-3.1C17.3 1.8 14.8 1 12 1 7.4 1 3.6 3.6 1.7 7.4l3.7 2.9C6.3 7.4 8.9 5 12 5z"/>
                <path fill="#4285F4" d="M23.5 12.3c0-.8-.1-1.7-.2-2.3H12v4.6h6.5c-.3 1.5-1.1 2.8-2.4 3.7l3.7 2.9c2.2-2 3.7-5 3.7-8.9z"/>
                <path fill="#FBBC05" d="M5.4 14.7c-.2-.7-.4-1.4-.4-2.2s.2-1.5.4-2.2L1.7 7.4C.6 9.6 0 12 0 14.7s.6 5.1 1.7 7.3l3.7-2.9z"/>
                <path fill="#34A853" d="M12 23.5c3.2 0 6-1.1 8-3l-3.7-2.9c-1.1.7-2.5 1.2-4.3 1.2-3.1 0-5.7-2.1-6.6-5l-3.7 2.9c1.9 3.8 5.7 6.8 10.3 6.8z"/>
              </svg>
              Google 계정으로 계속하기
            </button>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
};
