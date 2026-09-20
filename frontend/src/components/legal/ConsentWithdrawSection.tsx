'use client';

import React, { useState } from 'react';
import { useAuth } from '@/context/AuthContext';
import { AlertTriangle, CheckCircle, ShieldAlert } from 'lucide-react';

export function ConsentWithdrawSection() {
  const { user, isConsentRecorded, withdrawConsent } = useAuth();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [resultMessage, setResultMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const handleConfirmWithdraw = async () => {
    setIsSubmitting(true);
    setResultMessage(null);
    try {
      const ok = await withdrawConsent();
      if (ok) {
        setResultMessage({
          type: 'success',
          text: '서비스 이용 동의가 성공적으로 철회되었습니다. 새로운 상담 이용은 중단되며, 기존 상담 기록 열람 및 삭제 권리는 계속 보장됩니다.',
        });
        setIsModalOpen(false);
      } else {
        setResultMessage({
          type: 'error',
          text: '동의 철회 처리에 실패했습니다. 이미 철회되었거나 유효한 동의 이력이 없을 수 있습니다.',
        });
        setIsModalOpen(false);
      }
    } catch {
      setResultMessage({
        type: 'error',
        text: '오류가 발생했습니다. 잠시 후 다시 시도해 주세요.',
      });
      setIsModalOpen(false);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="mt-4 p-4 rounded-lg bg-stone-900/80 border border-stone-800 space-y-3">
      <div className="flex items-center gap-2 text-stone-200 font-medium text-xs sm:text-sm">
        <ShieldAlert className="w-4 h-4 text-amber-500" />
        <span>서비스 이용 동의 철회 안내 및 신청</span>
      </div>

      <p className="text-xs text-stone-400 leading-relaxed">
        이용자는 언제든지 본 서비스에 대한 이용약관 및 개인정보 수집·이용 동의를 철회할 권리가 있습니다.
        동의를 철회하더라도 개인정보보호법에 따라 <strong>기존 상담 기록 열람 및 즉시 삭제 권리는 그대로 유지</strong>됩니다.
      </p>

      {resultMessage && (
        <div
          className={`p-3 rounded text-xs flex items-start gap-2 ${
            resultMessage.type === 'success'
              ? 'bg-emerald-950/50 border border-emerald-800/60 text-emerald-300'
              : 'bg-red-950/50 border border-red-800/60 text-red-300'
          }`}
        >
          {resultMessage.type === 'success' ? (
            <CheckCircle className="w-4 h-4 shrink-0 text-emerald-400 mt-0.5" />
          ) : (
            <AlertTriangle className="w-4 h-4 shrink-0 text-red-400 mt-0.5" />
          )}
          <span>{resultMessage.text}</span>
        </div>
      )}

      <div>
        {!user ? (
          <p className="text-xs text-stone-500 italic">
            ※ 동의 철회를 신청하시려면 상단 메뉴에서 먼저 로그인해 주시기 바랍니다.
          </p>
        ) : !isConsentRecorded && resultMessage?.type === 'success' ? (
          <span className="inline-block px-3 py-1.5 rounded text-xs bg-stone-800 text-stone-400">
            현재 동의 철회 완료 상태입니다
          </span>
        ) : (
          <button
            type="button"
            onClick={() => setIsModalOpen(true)}
            className="px-3 py-1.5 rounded text-xs font-medium bg-red-950/40 hover:bg-red-900/60 text-red-300 border border-red-800/60 transition-colors"
          >
            서비스 이용 동의 철회하기
          </button>
        )}
      </div>

      {/* 동의 철회 확인 모달 */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="max-w-md w-full rounded-xl bg-stone-900 border border-stone-800 p-5 space-y-4 shadow-2xl">
            <div className="flex items-center gap-2 text-red-400 font-semibold text-sm sm:text-base border-b border-stone-800 pb-3">
              <AlertTriangle className="w-5 h-5" />
              <span>서비스 이용 동의를 철회하시겠습니까?</span>
            </div>

            <div className="space-y-2 text-xs text-stone-300 leading-relaxed">
              <p className="text-stone-200">
                동의 철회는 되돌리기 어려운 결정입니다. 다음 사항을 반드시 확인해 주시기 바랍니다:
              </p>
              <ul className="list-disc pl-5 space-y-1 text-stone-400">
                <li>
                  <strong className="text-stone-200">상담 이용 중단:</strong> 신규 주역 상담 및 후속 대화 생성이 즉시 차단됩니다.
                </li>
                <li>
                  <strong className="text-stone-200">데이터 권리 보장:</strong> 기존에 작성된 상담 기록의 열람 및 영구 삭제는 제한 없이 계속 가능합니다.
                </li>
                <li>
                  <strong className="text-stone-200">서비스 재이용:</strong> 추후 다시 상담을 진행하려면 로그인 시 이용약관 및 개인정보처리방침에 다시 동의하셔야 합니다.
                </li>
              </ul>
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-stone-800">
              <button
                type="button"
                disabled={isSubmitting}
                onClick={() => setIsModalOpen(false)}
                className="px-3 py-1.5 rounded text-xs font-medium bg-stone-800 hover:bg-stone-700 text-stone-300 transition-colors"
              >
                취소
              </button>
              <button
                type="button"
                disabled={isSubmitting}
                onClick={handleConfirmWithdraw}
                className="px-3 py-1.5 rounded text-xs font-medium bg-red-700 hover:bg-red-600 text-white transition-colors flex items-center gap-1.5"
              >
                {isSubmitting ? '처리 중...' : '동의 철회 확정'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
