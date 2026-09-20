'use client';

import React from 'react';
import Link from 'next/link';
import { LegalHeader } from '../../components/layout/LegalHeader';
import { Footer } from '../../components/layout/Footer';
import { Sparkles, AlertTriangle, ShieldCheck, Gift, Clock, HelpCircle } from 'lucide-react';
import { usePublicConfig } from '../../lib/publicConfig';

export default function PricingPage() {
  const { config, isFreeBetaActive } = usePublicConfig();

  const stageTitle = isFreeBetaActive
    ? '현재 단계: 무료 공개 베타 (Free Beta)'
    : '현재 단계: 무료 베타 준비 중 (Preparing Free Beta)';

  return (
    <div className="min-h-screen bg-stone-950 text-stone-200 flex flex-col font-sans selection:bg-amber-900 selection:text-amber-100">
      <LegalHeader
        title="이용 요금 및 결제 안내"
        subtitle="무료 베타 운영 정책 및 향후 정식 서비스 요금 안내"
        badgeText={isFreeBetaActive ? '무료 베타 (공식 운영)' : '베타 준비 중'}
      />

      <main className="flex-1 max-w-4xl w-full mx-auto px-4 py-8 sm:px-6 space-y-8 text-sm leading-relaxed">
        {/* 현재 단계 안내 배너 */}
        <div className="p-5 rounded-2xl bg-stone-900/80 border border-stone-800 text-stone-200 space-y-2">
          <div className="flex items-center gap-2 font-medium text-amber-400">
            <Gift className="w-5 h-5 shrink-0" />
            <span className="text-base font-semibold">{stageTitle}</span>
          </div>
          <p className="text-xs text-stone-300 leading-relaxed">
            마음지기(주역 심층 AI 성찰 서비스)는 현재 <strong>무료 베타 운영 단계</strong>에 있습니다.
            신규 가입 시 기본 웰컴 크레딧({config.welcome_credits}C)이 제공되며, 크레딧 소진 시에도 12시간마다 최대 {config.free_beta_refill_credits || 50}C까지 무료 자동 충전되어 주역 성찰 상담 기능(대화 1회당 {config.consultation_credit_cost}C)을 지속적으로 경험해 보실 수 있습니다.
          </p>
        </div>

        {/* 유료 상품 판매 상태 및 정책 현황 */}
        <section className="p-5 rounded-2xl bg-stone-900/60 border border-stone-800 space-y-4">
          <div className="flex items-center gap-2 text-stone-100 font-semibold text-base border-b border-stone-800 pb-2">
            <AlertTriangle className="w-4 h-4 text-amber-500" />
            <span>유료 판매 기능 상태 및 정책 현황</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
            <div className="p-4 rounded-xl bg-stone-950 border border-stone-800/80 space-y-2">
              <span className="font-semibold text-amber-400 flex items-center gap-1.5">
                <ShieldCheck className="w-4 h-4" /> 유료 결제 기능 비활성
              </span>
              <p className="text-stone-300 font-medium">
                현재 유료 판매 미실시 (무료 베타)
              </p>
              <p className="text-stone-400 leading-relaxed">
                전자지급결제대행사(PG) 연동 및 실제 유료 결제 경로는 현재 비활성화(purchase_enabled={String(config.purchase_enabled)}) 상태이며, 현재 본 서비스에서는 유료 결제 상품 및 유료 충전 기능을 제공하지 않습니다.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-stone-950 border border-stone-800/80 space-y-2">
              <span className="font-semibold text-amber-400 flex items-center gap-1.5">
                <Clock className="w-4 h-4" /> 향후 유료 요금제 안내
              </span>
              <p className="text-stone-300 font-medium">
                정식 유료화 시 별도 사전 공지 예정
              </p>
              <p className="text-stone-400 leading-relaxed">
                정식 유료화 전환 시의 유료 크레딧 패키지 구성, 가격, 결제 수단, 크레딧 유효기간 등은 향후 정식 유료 서비스 개시 전에 전자상거래법에 따라 공식 공지될 예정입니다.
              </p>
            </div>
          </div>

          <div className="p-3 rounded-lg bg-stone-900/40 border border-stone-800/60 text-xs text-stone-400 space-y-1">
            <p className="text-stone-300 font-medium">💡 크레딧 차감 및 보호 기준:</p>
            <p>• <strong>위기 차단 시 미차감:</strong> 심리적 위기 신호 감지(BLOCK_CRISIS) 시 상담을 긴급 전문 지원 채널로 즉시 안전 전환하며 크레딧은 차감되지 않습니다.</p>
            <p>• <strong>시스템 오류 시 복구:</strong> 시스템 장애나 네트워크 오류로 상담 턴이 정상 완료되지 못한 경우, 차감 예약된 크레딧은 자동으로 안전하게 복구됩니다.</p>
          </div>
        </section>

        {/* 향후 정식 서비스 전환 및 공지 안내 */}
        <section className="p-5 rounded-2xl bg-stone-900/40 border border-stone-800/80 space-y-3">
          <h2 className="text-base font-semibold text-stone-100 flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-amber-500" />
            향후 정식 유료화 전환 절차 안내
          </h2>
          <div className="space-y-2 text-xs text-stone-300 leading-relaxed">
            <p>
              1. <strong>사전 공지 의무:</strong> 유료 상품 도입 및 정식 서비스 전환 시에는 최소 14일 전 웹사이트 공지사항과 이메일을 통해 유료 상품 요금표(D07), 결제 수단(D09), 환불 정책(D08)을 공지합니다.
            </p>
            <p>
              2. <strong>청약철회 및 권리 보장:</strong> 향후 유료 상품 도입 시에는 전자상거래법에 따른 청약철회 및 공정한 비례 잔액 환불(D08) 규정이 적용될 예정입니다. 상세 내용은 <Link href="/refund" className="text-amber-400 underline">환불 및 청약철회 정책</Link>을 참고해 주시기 바랍니다.
            </p>
          </div>
        </section>

        {/* 안내 문의 */}
        <section className="p-4 rounded-xl bg-stone-900/40 border border-stone-800/80 text-xs text-stone-400 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <HelpCircle className="w-4 h-4 text-amber-500 shrink-0" />
            <span>요금 정책이나 서비스 준비 상황에 관한 의견이 있으신가요?</span>
          </div>
          <Link href="/contact" className="text-amber-400 hover:text-amber-300 underline font-medium">
            고객지원에 문의하기
          </Link>
        </section>
      </main>

      <Footer />
    </div>
  );
}
