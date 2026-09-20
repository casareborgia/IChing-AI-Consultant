'use client';

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, User, ShieldAlert, LogOut, Trash2, BookOpen } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import { deleteMyAccountApi } from '@/lib/api';

interface AccountModalProps {
  isOpen: boolean;
  onClose: () => void;
  onOpenHistory?: () => void;
}

export const AccountModal: React.FC<AccountModalProps> = ({ isOpen, onClose, onOpenHistory }) => {
  const { user, profile, session, signOut } = useAuth();
  const [showConfirmDelete, setShowConfirmDelete] = useState<boolean>(false);
  const [isDeleting, setIsDeleting] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  if (!isOpen || !user) return null;

  const handleDeleteAccount = async () => {
    if (!session?.access_token) return;
    setIsDeleting(true);
    setErrorMessage(null);
    try {
      const res = await deleteMyAccountApi(session.access_token);
      if (res.auth_account_deleted === false) {
        alert(
          '상담 기록은 모두 파기되었습니다. 다만 로그인 계정 삭제가 완료되지 않았습니다.\n\n고객지원(/contact)으로 문의해 주시기 바랍니다.'
        );
      } else {
        alert('회원 탈퇴 및 모든 개인 데이터가 영구적으로 파기되었습니다.');
      }
      onClose();
      await signOut();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '회원 탈퇴 처리에 실패했습니다.';
      setErrorMessage(msg);
      setIsDeleting(false);
    }
  };

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
          className="relative w-full max-w-md overflow-hidden rounded-3xl border border-stone-800/80 bg-stone-900 p-6 shadow-2xl text-stone-200 space-y-6"
        >
          {/* Header */}
          <div className="flex items-center justify-between border-b border-stone-800 pb-4">
            <div className="flex items-center space-x-2.5">
              <div className="w-9 h-9 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400">
                <User className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-stone-100">내 계정 관리</h3>
                <p className="text-xs text-stone-400">가입 정보 및 개인정보 관리</p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-stone-400 hover:text-stone-100 hover:bg-stone-800 transition"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* 에러 알림 */}
          {errorMessage && (
            <div className="p-3 rounded-xl bg-red-950/50 border border-red-800 text-xs text-red-300">
              ⚠️ {errorMessage}
            </div>
          )}

          {/* User Info Card */}
          <div className="rounded-2xl border border-stone-800 bg-stone-950/60 p-4 space-y-2.5 text-xs">
            <div className="flex justify-between items-center">
              <span className="text-stone-400">로그인 계정</span>
              <span className="font-mono text-stone-200 font-medium">{user.email}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-stone-400">보유 크레딧</span>
              <div className="text-right">
                <span className="font-bold text-amber-400 text-sm font-mono">
                  {profile?.credit !== null && profile?.credit !== undefined ? `${profile.credit} C` : '-'}
                </span>
                <p className="text-[10px] text-stone-500">12시간마다 최대 50C 자동 충전</p>
              </div>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-stone-400">계정 상태</span>
              <span className="text-emerald-400 font-medium">정상 이용 중</span>
            </div>
          </div>

          {/* 기록 보관함 및 로그아웃 액션 */}
          <div className="space-y-2 pt-1">
            {onOpenHistory && (
              <button
                onClick={() => {
                  onClose();
                  onOpenHistory();
                }}
                className="w-full flex items-center justify-center space-x-2 py-2.5 rounded-xl bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/30 text-amber-300 text-xs font-medium transition cursor-pointer"
              >
                <BookOpen className="w-4 h-4 text-amber-400" />
                <span>📜 내 상담 기록 & 저널 보관함</span>
              </button>
            )}
            <button
              onClick={async () => {
                onClose();
                await signOut();
              }}
              className="w-full flex items-center justify-center space-x-2 py-2.5 rounded-xl bg-stone-800 hover:bg-stone-700 text-stone-300 text-xs font-medium transition cursor-pointer"
            >
              <LogOut className="w-4 h-4" />
              <span>로그아웃</span>
            </button>
          </div>

          {/* Danger Zone: 회원 탈퇴 */}
          <div className="pt-2 border-t border-stone-800/80 space-y-3">
            <div className="text-xs text-stone-500 font-medium">개인정보 자기결정권 (잊힐 권리)</div>

            {!showConfirmDelete ? (
              <button
                onClick={() => setShowConfirmDelete(true)}
                className="w-full flex items-center justify-center space-x-1.5 py-2 rounded-xl border border-red-900/40 bg-red-950/20 hover:bg-red-950/40 text-red-400 text-xs transition"
              >
                <Trash2 className="w-3.5 h-3.5" />
                <span>회원 탈퇴 및 모든 데이터 영구 파기</span>
              </button>
            ) : (
              <div className="p-4 rounded-2xl bg-red-950/40 border border-red-800/80 space-y-3">
                <div className="flex items-start space-x-2 text-red-300 text-xs">
                  <ShieldAlert className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
                  <div className="space-y-1">
                    <p className="font-bold text-red-200">정말 탈퇴하시겠습니까?</p>
                    <p className="text-[11px] text-red-300/90 leading-relaxed">
                      탈퇴 시 보유 중인 잔여 크레딧({profile?.credit || 0}C)과 모든 상담 기록, 성찰 저널이 즉시 영구 삭제되며 복구할 수 없습니다.
                    </p>
                  </div>
                </div>

                <div className="flex space-x-2 pt-1">
                  <button
                    onClick={() => setShowConfirmDelete(false)}
                    disabled={isDeleting}
                    className="flex-1 py-2 rounded-xl bg-stone-800 hover:bg-stone-700 text-stone-300 text-xs font-medium transition"
                  >
                    취소
                  </button>
                  <button
                    onClick={handleDeleteAccount}
                    disabled={isDeleting}
                    className="flex-1 py-2 rounded-xl bg-red-600 hover:bg-red-700 text-white text-xs font-bold transition disabled:opacity-50"
                  >
                    {isDeleting ? '파기 처리 중...' : '탈퇴 확정 (영구 파기)'}
                  </button>
                </div>
              </div>
            )}
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
};
