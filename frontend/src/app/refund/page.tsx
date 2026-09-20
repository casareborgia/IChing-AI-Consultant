import React from 'react';
import Link from 'next/link';
import { LegalHeader } from '../../components/layout/LegalHeader';
import { Footer } from '../../components/layout/Footer';
import { RefreshCw, Calculator, Clock, CheckCircle2, ShieldCheck } from 'lucide-react';
import { LEGAL_DOCUMENTS_VERSION } from '../../lib/legalVersion';

export default function RefundPage() {
  return (
    <div className="min-h-screen bg-stone-950 text-stone-200 flex flex-col font-sans selection:bg-amber-900 selection:text-amber-100">
      <LegalHeader
        title="환불 및 청약철회 정책"
        subtitle="현재 무료 베타 운영 및 향후 유료 판매 시 적용될 청약철회 기준"
        badgeText={LEGAL_DOCUMENTS_VERSION}
      />

      <main className="flex-1 max-w-4xl w-full mx-auto px-4 py-8 sm:px-6 space-y-8 text-sm leading-relaxed">
        {/* 최우선 안내: 유료 결제 미제공 및 향후 환불 정책 사전 고지 배너 */}
        <div className="p-5 rounded-2xl bg-amber-500/10 border border-amber-500/30 text-amber-200 space-y-2">
          <div className="flex items-center gap-2 font-medium text-amber-300">
            <ShieldCheck className="w-5 h-5 shrink-0 text-amber-400" />
            <span className="text-base font-semibold">현재 단계: 무료 베타 운영 (유료 판매 미실시 및 사전 고지)</span>
          </div>
          <p className="text-xs text-amber-300/90 leading-relaxed">
            주역 심층 AI 상담 서비스는 현재 무료 베타 운영 단계로, 유료 결제 상품을 판매하지 않습니다.
            아래 내용은 향후 유료 판매 개시 시 전자상거래 등에서의 소비자보호에 관한 법률 등 관련 법령을 준수하기 위해 사전에 안내하는 <strong>공식 청약철회 및 환불 규정</strong>입니다.
          </p>
        </div>

        {/* 1. 기본 청약철회 권리 (향후 유료화 시 적용 예정안) */}
        <section className="space-y-3">
          <h2 className="text-base font-semibold text-stone-100 flex items-center gap-2 border-b border-stone-800 pb-2">
            <RefreshCw className="w-4 h-4 text-amber-500" />
            1. 기본 청약철회 권리 (향후 유료 서비스 도입 시 기준안)
          </h2>
          <div className="space-y-2 text-stone-300">
            <p>
              1. <strong>전액 미사용 크레딧:</strong> 향후 유료 크레딧 상품을 구매하고 전혀 사용하지 않은 경우, 결제일로부터 <strong>7일 이내</strong>에 위약금 없이 결제 대금 전액을 청약철회(환불)할 수 있도록 설계할 예정입니다.
            </p>
            <p>
              2. <strong>가분적 잔여 크레딧 환불:</strong> 일부 크레딧을 사용하여 상담을 진행하였더라도, 남은 유료 크레딧에 비례하여 잔액 환불을 신청할 수 있는 공정한 환불 기준을 수립할 예정입니다.
            </p>
          </div>
        </section>

        {/* 2. 환불 금액 산정 공식 (D08 설계 검토 예시안) */}
        <section className="space-y-3">
          <h2 className="text-base font-semibold text-stone-100 flex items-center gap-2 border-b border-stone-800 pb-2">
            <Calculator className="w-4 h-4 text-amber-500" />
            2. 소비 순서 및 잔액 환불 산정 기준 (D08 설계 검토 예시안)
          </h2>
          <div className="p-4 rounded-xl bg-stone-900/60 border border-stone-800 space-y-3">
            <div className="text-xs text-stone-400">
              <span className="font-semibold text-stone-200">※ 본 계산 공식은 향후 유료화 정책 수립을 위한 내부 검토 예시안입니다:</span>
            </div>
            <div className="text-xs text-stone-300 font-mono bg-stone-950 p-3 rounded-lg border border-stone-800">
              환급 금액 = 실결제 금액 × (남은 유료 크레딧 수량 ÷ 구매한 유료 크레딧 수량)
            </div>
            <div className="space-y-2 text-xs text-stone-400">
              <p className="text-stone-300 font-medium">💡 검토 예시 시나리오:</p>
              <ul className="list-disc pl-5 space-y-1">
                <li>유료 크레딧을 구매하고 프로모션 무료 보너스 크레딧을 함께 수령한 경우, 무료 보너스 크레딧이 우선 차감됩니다.</li>
                <li>무료로 지급된 웰컴 크레딧 및 이벤트 보너스는 현금 환급 대상에서 제외됩니다.</li>
                <li>구체적인 환불 산정 기준 및 수수료 정책은 정식 유료 상품 출시 시 운영자 결정 후 확정 공지됩니다.</li>
              </ul>
            </div>
          </div>
        </section>

        {/* 3. 환급 기한 및 절차 원칙 */}
        <section className="space-y-3">
          <h2 className="text-base font-semibold text-stone-100 flex items-center gap-2 border-b border-stone-800 pb-2">
            <Clock className="w-4 h-4 text-amber-500" />
            3. 환급 처리 기한 및 수수료 원칙 (준비안)
          </h2>
          <div className="space-y-2 text-stone-300">
            <p>
              1. <strong>3영업일 내 처리 지향:</strong> 정식 유료화 시 환불 접수 확인일로부터 3영업일 이내에 결제 취소 또는 환급 절차를 완료하는 것을 기본 원칙으로 합니다.
            </p>
            <p>
              2. <strong>수수료 정책:</strong> 법정 청약철회 시 부당한 위약금이나 수수료를 고객에게 전가하지 않는 0원 수수료를 지향하여 정책을 수립할 예정입니다.
            </p>
          </div>
        </section>

        {/* 4. 문의 창구 */}
        <section className="space-y-3">
          <h2 className="text-base font-semibold text-stone-100 flex items-center gap-2 border-b border-stone-800 pb-2">
            <CheckCircle2 className="w-4 h-4 text-amber-500" />
            4. 정책 문의 창구
          </h2>
          <p className="text-stone-300">
            환불 정책 및 서비스 이용에 관한 문의는 <Link href="/contact" className="text-amber-400 underline font-medium">고객지원 센터</Link>를 통해 접수해 주시면 성실히 안내해 드리겠습니다.
          </p>
        </section>
      </main>

      <Footer />
    </div>
  );
}
