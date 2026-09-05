'use client';

import React from 'react';
import { 
  Compass, 
  BookOpen, 
  Sparkles, 
  ShieldCheck, 
  Scale, 
  MessageSquare,
  Gift,
  ArrowRight,
  FileText
} from 'lucide-react';

interface MicroLandingSectionProps {
  onSelectQuestion: (question: string) => void;
}

export const MicroLandingSection: React.FC<MicroLandingSectionProps> = ({ onSelectQuestion }) => {
  return (
    <div className="mt-16 space-y-16 border-t border-stone-800/60 pt-16 text-stone-200">
      {/* 1. 웰컴 혜택 띠배너 */}
      <div className="rounded-2xl bg-gradient-to-r from-amber-950/40 via-stone-900/80 to-amber-950/30 border border-amber-500/20 p-5 sm:p-6 backdrop-blur-md flex flex-col sm:flex-row items-center justify-between gap-4 shadow-xl">
        <div className="flex items-center gap-3.5 text-left">
          <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400 shrink-0">
            <Gift className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold uppercase tracking-wider text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20">
                웰컴 프로모션
              </span>
              <span className="text-xs text-stone-400">무료 체험</span>
            </div>
            <h4 className="text-sm sm:text-base font-serif font-medium text-stone-100 mt-1">
              신규 가입 시 <span className="text-amber-300 font-semibold">50 웰컴 크레딧</span>이 즉시 지급됩니다
            </h4>
            <p className="text-xs text-stone-400 font-light mt-0.5">
              별도의 결제 정보 없이 <strong className="text-amber-400 font-normal">심층 괘해석 리포트 발급</strong> 및 1:1 AI 성찰 대화를 무료로 경험해 보세요.
            </p>
          </div>
        </div>

        <button 
          onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
          className="w-full sm:w-auto shrink-0 px-4 py-2.5 rounded-xl bg-amber-500/20 hover:bg-amber-500/30 border border-amber-500/40 text-amber-300 text-xs font-medium transition-all flex items-center justify-center gap-1.5 cursor-pointer"
        >
          <span>지금 질문해보기</span>
          <ArrowRight className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* 2. 기존 상담 프로세스 순서에 '레포트 생성' 삽입 (4단계 프로세스) */}
      <section className="space-y-6 text-center">
        <div>
          <span className="text-[11px] font-mono tracking-widest text-amber-500/80 uppercase block mb-1">
            CONSULTATION PROCESS
          </span>
          <h3 className="text-xl sm:text-2xl font-serif font-semibold text-stone-100">
            성찰 대화는 어떻게 진행되나요?
          </h3>
          <p className="text-xs sm:text-sm text-stone-400 font-light mt-2 max-w-xl mx-auto">
            주역의 전통 서법(筮法)과 현대 AI 상담학을 결합하여, 네 단계를 거쳐 마음의 흐름을 짚어냅니다.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 text-left">
          {/* Step 1 */}
          <div className="bg-stone-900/60 border border-stone-800/80 rounded-2xl p-5 backdrop-blur-sm relative overflow-hidden group hover:border-stone-700 transition">
            <div className="text-3xl font-serif text-amber-500/20 absolute top-4 right-4 font-bold">
              01
            </div>
            <div className="w-9 h-9 rounded-lg bg-stone-800/80 flex items-center justify-center text-amber-400 mb-3.5">
              <MessageSquare className="w-4 h-4" />
            </div>
            <h4 className="text-sm font-semibold text-stone-100 font-serif">1. 마음과 질문 정리</h4>
            <p className="text-xs text-stone-400 font-light mt-1.5 leading-relaxed">
              복잡하고 조급한 마음을 차분히 정리합니다. 이전 상담과의 연속성을 살피고 고민의 본질을 1문장으로 정돈합니다.
            </p>
          </div>

          {/* Step 2 */}
          <div className="bg-stone-900/60 border border-stone-800/80 rounded-2xl p-5 backdrop-blur-sm relative overflow-hidden group hover:border-stone-700 transition">
            <div className="text-3xl font-serif text-amber-500/20 absolute top-4 right-4 font-bold">
              02
            </div>
            <div className="w-9 h-9 rounded-lg bg-stone-800/80 flex items-center justify-center text-amber-400 mb-3.5">
              <Compass className="w-4 h-4" />
            </div>
            <h4 className="text-sm font-semibold text-stone-100 font-serif">2. 주자 변효 괘 도출</h4>
            <p className="text-xs text-stone-400 font-light mt-1.5 leading-relaxed">
              동전 3개 서법으로 64괘 384효 중 마주한 본괘(현재)와 지괘(변화의 방향), 그리고 핵심 초점 효사를 엄밀히 산출합니다.
            </p>
          </div>

          {/* Step 3 (기존 순서에 들어가는 레포트 생성 단계) */}
          <div className="bg-stone-900/60 border border-amber-500/30 rounded-2xl p-5 backdrop-blur-sm relative overflow-hidden group hover:border-amber-500/50 transition">
            <div className="text-3xl font-serif text-amber-500/30 absolute top-4 right-4 font-bold">
              03
            </div>
            <div className="w-9 h-9 rounded-lg bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-300 mb-3.5">
              <FileText className="w-4 h-4" />
            </div>
            <h4 className="text-sm font-semibold text-amber-200 font-serif">3. 괘해석 리포트 생성</h4>
            <p className="text-xs text-stone-400 font-light mt-1.5 leading-relaxed">
              도출된 괘상과 원문 주석을 바탕으로 진단·행동지침·경계·미래귀결 4단계 심층 맞춤 컨설팅 리포트를 집필합니다.
            </p>
          </div>

          {/* Step 4 */}
          <div className="bg-stone-900/60 border border-stone-800/80 rounded-2xl p-5 backdrop-blur-sm relative overflow-hidden group hover:border-stone-700 transition">
            <div className="text-3xl font-serif text-amber-500/20 absolute top-4 right-4 font-bold">
              04
            </div>
            <div className="w-9 h-9 rounded-lg bg-stone-800/80 flex items-center justify-center text-amber-400 mb-3.5">
              <BookOpen className="w-4 h-4" />
            </div>
            <h4 className="text-sm font-semibold text-stone-100 font-serif">4. 1:1 심층 성찰 대화</h4>
            <p className="text-xs text-stone-400 font-light mt-1.5 leading-relaxed">
              완성된 리포트를 숙고한 후 수석 AI 상담사와 1:1 대화를 나누며 스스로 해답을 발견하도록 돕습니다.
            </p>
          </div>
        </div>
      </section>

      {/* 3. 왜 단순 점술/운세와 다른가? (3대 차별점) */}
      <section className="space-y-6">
        <div className="text-center">
          <span className="text-[11px] font-mono tracking-widest text-amber-500/80 uppercase block mb-1">
            CORE PHILOSOPHY
          </span>
          <h3 className="text-xl sm:text-2xl font-serif font-semibold text-stone-100">
            단순 점술·타로와 어떻게 다른가요?
          </h3>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-gradient-to-b from-stone-900/80 to-stone-950 border border-stone-800/80 rounded-2xl p-5">
            <div className="flex items-center gap-2 text-amber-400 text-xs font-semibold mb-2">
              <Scale className="w-4 h-4" />
              <span>주체적 성찰의 거울</span>
            </div>
            <h4 className="text-sm font-medium text-stone-100">단정적 예언 ❌ / 내면 성찰 ⭕</h4>
            <p className="text-xs text-stone-400 font-light mt-2 leading-relaxed">
              "합격한다/불합격한다"는 공포 마케팅이나 운명론적 단정을 거부합니다. 지금 어떤 태도로 상황에 임해야 하는지 성찰의 질문을 건넵니다.
            </p>
          </div>

          <div className="bg-gradient-to-b from-stone-900/80 to-stone-950 border border-stone-800/80 rounded-2xl p-5">
            <div className="flex items-center gap-2 text-amber-400 text-xs font-semibold mb-2">
              <BookOpen className="w-4 h-4" />
              <span>2,536건 문헌 근거</span>
            </div>
            <h4 className="text-sm font-medium text-stone-100">근거 없는 잡담 ❌ / 원문 심층 리포트 ⭕</h4>
            <p className="text-xs text-stone-400 font-light mt-2 leading-relaxed">
              출처 불명의 환각을 배제하고, 『이천역전』(정전)과 주자 『본의』의 역사적 원문에 기반해 1:1 맞춤 컨설팅 리포트를 발급합니다.
            </p>
          </div>

          <div className="bg-gradient-to-b from-stone-900/80 to-stone-950 border border-stone-800/80 rounded-2xl p-5">
            <div className="flex items-center gap-2 text-amber-400 text-xs font-semibold mb-2">
              <ShieldCheck className="w-4 h-4" />
              <span>제로 트러스트 안전</span>
            </div>
            <h4 className="text-sm font-medium text-stone-100">사생활 노출 ❌ / 위기 안전 보호 ⭕</h4>
            <p className="text-xs text-stone-400 font-light mt-2 leading-relaxed">
              식약처 웰니스 가이드를 준수하며, 위기 신호 감지 시 즉시 서비스를 중단하고 109 자살예방 공공 핫라인으로 안전하게 이관합니다.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
};
