import React from 'react';
import { LegalHeader } from '../../components/layout/LegalHeader';
import { Footer } from '../../components/layout/Footer';
import { Sparkles, Brain, Compass, ShieldAlert } from 'lucide-react';
import { LEGAL_DOCUMENTS_VERSION } from '../../lib/legalVersion';

export default function AiNoticePage() {
  return (
    <div className="min-h-screen bg-stone-950 text-stone-200 flex flex-col font-sans selection:bg-amber-900 selection:text-amber-100">
      <LegalHeader
        title="AI 서비스 투명성 고지"
        subtitle="인공지능 기본법 관련 지침 및 서비스 성격에 관한 투명성 고지"
        badgeText={LEGAL_DOCUMENTS_VERSION}
      />

      <main className="flex-1 max-w-4xl w-full mx-auto px-4 py-8 sm:px-6 space-y-8 text-sm leading-relaxed">
        {/* 인공지능 기본법 제31조 안내 */}
        <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-200/90 space-y-1">
          <div className="flex items-center gap-2 font-medium">
            <Sparkles className="w-4 h-4 text-amber-400 shrink-0" />
            <span>생성형 인공지능(Generative AI) 기반 결과물 표시</span>
          </div>
          <p className="text-xs text-amber-300/80 leading-relaxed">
            본 서비스의 대화 응답, 괘 해석 리포트, 그리고 회고 카드는 최신 거대언어모델(LLM)에 기반한 생성형 인공지능이 생성한 저작물입니다.
            인공지능 발전과 신뢰 기반 조성 등에 관한 법률 지침 및 AI 기본법 제31조 취지에 부합하도록, 본 서비스가 인공지능 기반 성찰 도구임을 명확히 안내합니다.
          </p>
        </div>

        {/* 1. 고전 주역 원문과 AI 해석의 엄격한 구분 */}
        <section className="space-y-3">
          <h2 className="text-base font-semibold text-stone-100 flex items-center gap-2 border-b border-stone-800 pb-2">
            <Compass className="w-4 h-4 text-amber-500" />
            1. 고전 주역 원문과 AI 생성 해석의 구별
          </h2>
          <div className="space-y-2 text-stone-300">
            <p>
              1. <strong>고전 원문 데이터:</strong> 64괘 386효의 괘사·효사 및 송대 정이천의 『이천역전(伊川易傳)』, 주자의 『주역본의(周易本義)』 주석은 역사적 문헌(Kanseki Repository 표점본)에서 엄격하게 1:1로 직접 인출한 원전 자료입니다.
            </p>
            <p>
              2. <strong>AI 생성 해석 및 상담:</strong> 원전의 비유와 상징을 이용자의 현대적 고민 사연에 1:1로 매핑하여 풀어내는 설명, 대화체 질문, 그리고 실천 다짐 카드는 <strong>생성형 AI 모델이 생성한 창작물</strong>입니다.
            </p>
          </div>
        </section>

        {/* 2. 서비스의 성격: 점술이나 예언이 아닌 '의사결정 성찰 도구' */}
        <section className="space-y-3">
          <h2 className="text-base font-semibold text-stone-100 flex items-center gap-2 border-b border-stone-800 pb-2">
            <Brain className="w-4 h-4 text-amber-500" />
            2. 예언·점단이 아닌 &apos;변화를 읽는 의사결정 성찰 도구&apos;
          </h2>
          <div className="space-y-2 text-stone-300">
            <p>
              본 서비스는 단순한 운세 풀이나 미래에 대한 길흉화복 단정이 목적이 아닙니다.
            </p>
            <p>
              주역의 본질인 <strong>&apos;변화(易)의 원리와 균형&apos;</strong>을 렌즈 삼아, 질문자 스스로 자신의 내면을 되돌아보고, 고정관념에서 벗어나 주체적으로 결정을 내릴 수 있도록 돕는 <strong>소크라테스식 되묻기 성찰 대화</strong>를 제공합니다.
            </p>
          </div>
        </section>

        {/* 3. 의료 및 전문 자문 면책 */}
        <section className="space-y-3">
          <h2 className="text-base font-semibold text-stone-100 flex items-center gap-2 border-b border-stone-800 pb-2">
            <ShieldAlert className="w-4 h-4 text-amber-500" />
            3. 의학적·법률적·금융적 진단 불가 고지
          </h2>
          <div className="space-y-2 text-stone-300">
            <p>
              1. 본 서비스의 AI는 공인된 정신과 전문의, 임상심리전문가, 변호사, 투자전문가가 아닙니다.
            </p>
            <p>
              2. 인공지능의 답변은 우울증, 불안장애 등 정신질환에 대한 의학적 진단이나 치료법이 될 수 없으며, 질병 치료 목적의 의료기기(SaMD)에 해당하지 않습니다.
            </p>
            <p>
              3. 중대한 심리적 위기나 고통이 있는 경우 반드시 전문 의료기관이나 <a href="/safety" className="text-amber-400 underline">국가 위기 상담 전화</a>의 도움을 받으셔야 합니다.
            </p>
          </div>
        </section>
      </main>

      <Footer />
    </div>
  );
}
