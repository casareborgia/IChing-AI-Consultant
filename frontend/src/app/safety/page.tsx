import React from 'react';
import { LegalHeader } from '../../components/layout/LegalHeader';
import { Footer } from '../../components/layout/Footer';
import { HeartHandshake, PhoneCall, Shield } from 'lucide-react';
import { LEGAL_DOCUMENTS_VERSION } from '../../lib/legalVersion';

export default function SafetyPage() {
  return (
    <div className="min-h-screen bg-stone-950 text-stone-200 flex flex-col font-sans selection:bg-amber-900 selection:text-amber-100">
      <LegalHeader
        title="위기 대응 및 긴급 지원 안내"
        subtitle="심리적 위기 상황 시 도움을 받을 수 있는 24시간 긴급 전문 지원 채널"
        badgeText={LEGAL_DOCUMENTS_VERSION}
      />

      <main className="flex-1 max-w-4xl w-full mx-auto px-4 py-8 sm:px-6 space-y-8 text-sm leading-relaxed">
        {/* 상단 긴급 배너 */}
        <div className="p-5 rounded-2xl bg-rose-500/10 border border-rose-500/30 text-rose-200 space-y-3">
          <div className="flex items-center gap-2.5 font-medium text-rose-300">
            <HeartHandshake className="w-5 h-5 shrink-0 text-rose-400" />
            <span className="text-base">혼자 힘들어하지 마세요. 지금 도움을 받으실 수 있습니다.</span>
          </div>
          <p className="text-xs text-rose-200/90 leading-relaxed">
            마음지기는 인공지능 기반의 주역 성찰 도구이므로 응급 심리 지원이나 인명 구조를 직접 수행할 수 없습니다.
            극심한 절망감, 자해나 자살 충동 등 심리적 위기 상황에 계시다면 즉시 아래의 <strong>전문 상담 기관</strong>으로 연락해 주시기 바랍니다.
          </p>
        </div>

        {/* 긴급 전문 상담 직통 전화 채널 (공식 기관) */}
        <section className="space-y-4">
          <h2 className="text-base font-semibold text-stone-100 flex items-center gap-2 border-b border-stone-800 pb-2">
            <PhoneCall className="w-4 h-4 text-amber-500" />
            24시간 무료 긴급 상담 기관 안내
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="p-4 rounded-xl bg-stone-900/70 border border-stone-800 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-amber-400">자살예방 상담전화</span>
                <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">24시간 운영</span>
              </div>
              <p className="text-2xl font-bold text-stone-100 font-mono tracking-wider">
                <a href="tel:109" className="hover:text-amber-300 transition underline decoration-amber-500/50">
                  109
                </a>
              </p>
              <p className="text-xs text-stone-400">
                보건복지부 주관 24시간 위기 전문 상담. 위급한 심리적 위기에 즉각적인 전문 상담을 제공합니다.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-stone-900/70 border border-stone-800 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-amber-400">정신건강 위기상담전화</span>
                <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">24시간 운영</span>
              </div>
              <p className="text-2xl font-bold text-stone-100 font-mono tracking-wider">
                <a href="tel:1577-0199" className="hover:text-amber-300 transition underline decoration-amber-500/50">
                  1577-0199
                </a>
              </p>
              <p className="text-xs text-stone-400">
                광역 및 기초 정신건강복지센터 연계. 전문가와의 심층 전화 상담 및 지역사회 치료 지원을 안내합니다.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-stone-900/70 border border-stone-800 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-amber-400">청소년 전화</span>
                <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">24시간 운영</span>
              </div>
              <p className="text-2xl font-bold text-stone-100 font-mono tracking-wider">
                <a href="tel:1388" className="hover:text-amber-300 transition underline decoration-amber-500/50">
                  1388
                </a>
              </p>
              <p className="text-xs text-stone-400">
                청소년 및 청소년 자녀를 둔 보호자를 위한 심리 상담 및 위기 개입을 지원합니다.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-stone-900/70 border border-stone-800 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-amber-400">경찰청 / 소방청 응급구조</span>
                <span className="text-[10px] px-2 py-0.5 rounded bg-rose-500/10 text-rose-400 border border-rose-500/20">긴급 출동</span>
              </div>
              <p className="text-2xl font-bold text-stone-100 font-mono tracking-wider">
                <a href="tel:112" className="hover:text-amber-300 transition underline mr-3">112</a>
                /
                <a href="tel:119" className="hover:text-amber-300 transition underline ml-3">119</a>
              </p>
              <p className="text-xs text-stone-400">
                신체적 위험이나 긴급한 안전 조치가 요구되는 즉각적인 위기 상황 시 주저 없이 신고해 주십시오.
              </p>
            </div>
          </div>
        </section>

        {/* 2. 서비스 내 AI 위기 스크리닝 정책 안내 */}
        <section className="space-y-3">
          <h2 className="text-base font-semibold text-stone-100 flex items-center gap-2 border-b border-stone-800 pb-2">
            <Shield className="w-4 h-4 text-amber-500" />
            서비스 내 안전 스크리닝 및 위기 개입 정책
          </h2>
          <div className="space-y-2 text-stone-300">
            <p>
              1. <strong>즉각적 긴급 전환:</strong> 상담 질문이나 대화 중 자해, 자살, 극단적 위기 신호가 감지될 경우, 시스템은 주역 점단 풀이를 즉시 중단하고 위의 공식 핫라인 지원 화면으로 안전하게 전환합니다.
            </p>
            <p>
              2. <strong>위기 차단 크레딧 미차감 (D05 구현 반영):</strong> 심리적 위기 신호 감지(BLOCK_CRISIS)로 상담이 안전 지원으로 전환된 경우 서버 규칙에 따라 크레딧은 절대 차감되지 않습니다 (0 크레딧 처리). 단, 일반 시스템 기술 장애에 대한 보상 기준은 별도 정책 검토 중입니다.
            </p>
            <p>
              3. <strong>24시간 안전 래치:</strong> 이용자의 안전을 우선하여, 위기 신호 감지 후 최소 24시간 동안은 괘 뽑기 대신 안정을 돕는 정적 긴급 채널을 최우선으로 안내합니다.
            </p>
          </div>
        </section>
      </main>

      <Footer />
    </div>
  );
}
