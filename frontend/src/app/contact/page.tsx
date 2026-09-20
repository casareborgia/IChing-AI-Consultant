'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { LegalHeader } from '../../components/layout/LegalHeader';
import { Footer } from '../../components/layout/Footer';
import { Send, CheckCircle, ShieldCheck } from 'lucide-react';
import { submitSupportInquiryApi } from '../../lib/api';
import { LEGAL_DOCUMENTS_VERSION } from '../../lib/legalVersion';

export default function ContactPage() {
  const [formData, setFormData] = useState({
    category: 'service',
    email: '',
    orderId: '',
    message: '',
  });

  const [submittedTicket, setSubmittedTicket] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.email || !formData.message) return;

    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      const res = await submitSupportInquiryApi({
        category: formData.category,
        email: formData.email,
        message: formData.message,
        order_id: formData.orderId ? formData.orderId.trim() : undefined,
      });
      setSubmittedTicket(res.ticket_no);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : '문의 접수 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.';
      setErrorMessage(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-stone-950 text-stone-200 flex flex-col font-sans selection:bg-amber-900 selection:text-amber-100">
      <LegalHeader
        title="고객지원 및 문의 센터"
        subtitle="마음지기 서비스 이용 문의, 결제/환불 요청, 데이터 삭제 및 권리행사 접수 창구"
        badgeText={LEGAL_DOCUMENTS_VERSION}
      />

      <main className="flex-1 max-w-3xl w-full mx-auto px-4 py-8 sm:px-6 space-y-8 text-sm leading-relaxed">
        {/* 상담 기록 직접 삭제 및 데이터 권리 안내 (AG-3) */}
        <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-200/90 space-y-1">
          <div className="flex items-center gap-2 font-medium">
            <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
            <span>상담 기록 직접 삭제 안내 (개인정보 자기결정권)</span>
          </div>
          <p className="text-xs text-stone-300 leading-relaxed">
            개별 상담 대화록 및 성찰 저널은 상담 완료 화면에서 <strong>[이 상담 기록 삭제]</strong> 버튼을 통해 즉시 영구 파기할 수 있습니다.{' '}
            <Link href="/" className="text-amber-400 underline underline-offset-2 hover:text-amber-300 transition">
              메인 화면으로 이동
            </Link>
          </p>
        </div>

        {submittedTicket ? (
          /* 제출 완료 화면 */
          <div className="p-6 rounded-2xl bg-stone-900/80 border border-stone-800 text-center space-y-4">
            <div className="w-12 h-12 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 mx-auto flex items-center justify-center">
              <CheckCircle className="w-6 h-6" />
            </div>
            <div className="space-y-1">
              <h3 className="text-lg font-semibold text-stone-100">문의가 정상 접수되었습니다</h3>
              <p className="text-xs text-stone-400">
                접수 번호: <span className="font-mono font-bold text-amber-400 text-sm">{submittedTicket}</span>
              </p>
            </div>
            <p className="text-xs text-stone-400 max-w-md mx-auto leading-relaxed">
              작성하신 답변 안내 이메일(<span className="text-stone-300 font-medium">{formData.email}</span>)로 접수 확인 정보가 기록되었습니다. 영업일 기준 24시간 이내에 담당자가 검토 후 안내드립니다.
            </p>
            <div className="pt-2">
              <button
                type="button"
                onClick={() => {
                  setSubmittedTicket(null);
                  setFormData({ category: 'service', email: '', orderId: '', message: '' });
                }}
                className="px-4 py-2 rounded-lg bg-stone-800 hover:bg-stone-700 text-xs font-medium text-stone-200 transition"
              >
                다른 문의 작성하기
              </button>
            </div>
          </div>
        ) : (
          /* 문의 작성 폼 */
          <form onSubmit={handleSubmit} className="p-6 rounded-2xl bg-stone-900/60 border border-stone-800 space-y-5">
            {errorMessage && (
              <div className="p-3 rounded-lg bg-rose-950/40 border border-rose-900/60 text-rose-300 text-xs">
                {errorMessage}
              </div>
            )}

            <div className="space-y-1">
              <label htmlFor="category" className="block text-xs font-medium text-stone-300">
                문의 유형 <span className="text-amber-500">*</span>
              </label>
              <select
                id="category"
                value={formData.category}
                onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                className="w-full bg-stone-950 border border-stone-800 rounded-lg px-3 py-2 text-xs text-stone-200 focus:outline-none focus:border-amber-500 transition"
              >
                <option value="service">일반 서비스 이용 문의</option>
                <option value="refund">결제 및 환불/청약철회 요청</option>
                <option value="privacy">개인정보 열람·삭제·동의철회 (권리행사)</option>
                <option value="safety">위기대응 및 오탐 이의제기</option>
                <option value="other">기타 제휴 및 제안</option>
              </select>
            </div>

            <div className="space-y-1">
              <label htmlFor="email" className="block text-xs font-medium text-stone-300">
                답변 수신용 이메일 주소 <span className="text-amber-500">*</span>
              </label>
              <input
                id="email"
                type="email"
                required
                placeholder="example@domain.com"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                className="w-full bg-stone-950 border border-stone-800 rounded-lg px-3 py-2 text-xs text-stone-200 focus:outline-none focus:border-amber-500 transition"
              />
            </div>

            {formData.category === 'refund' && (
              <div className="space-y-1">
                <label htmlFor="orderId" className="block text-xs font-medium text-stone-300">
                  주문번호 (선택사항)
                </label>
                <input
                  id="orderId"
                  type="text"
                  placeholder="예: ORD-2026..."
                  value={formData.orderId}
                  onChange={(e) => setFormData({ ...formData, orderId: e.target.value })}
                  className="w-full bg-stone-950 border border-stone-800 rounded-lg px-3 py-2 text-xs text-stone-200 focus:outline-none focus:border-amber-500 transition font-mono"
                />
              </div>
            )}

            <div className="space-y-1">
              <label htmlFor="message" className="block text-xs font-medium text-stone-300">
                문의 내용 <span className="text-amber-500">*</span>
              </label>
              <textarea
                id="message"
                required
                rows={5}
                placeholder="문의하실 내용을 상세히 적어주세요. (주민등록번호, 금융 비밀번호 등 민감정보는 입력하지 마십시오.)"
                value={formData.message}
                onChange={(e) => setFormData({ ...formData, message: e.target.value })}
                className="w-full bg-stone-950 border border-stone-800 rounded-lg p-3 text-xs text-stone-200 focus:outline-none focus:border-amber-500 transition resize-none"
              />
            </div>

            <div className="pt-2">
              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full py-2.5 px-4 rounded-lg bg-amber-600/90 hover:bg-amber-500 text-stone-950 font-semibold text-xs transition flex items-center justify-center gap-1.5 cursor-pointer disabled:opacity-50"
              >
                {isSubmitting ? (
                  <span>문의 접수 중...</span>
                ) : (
                  <>
                    <Send className="w-3.5 h-3.5" />
                    <span>문의 접수하기</span>
                  </>
                )}
              </button>
            </div>
          </form>
        )}
      </main>

      <Footer />
    </div>
  );
}
