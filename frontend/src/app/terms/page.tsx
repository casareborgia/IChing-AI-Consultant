import React from 'react';
import Link from 'next/link';
import { LegalHeader } from '../../components/layout/LegalHeader';
import { Footer } from '../../components/layout/Footer';
import { ShieldAlert, BookOpen, CheckCircle } from 'lucide-react';
import { LEGAL_DOCUMENTS_VERSION } from '../../lib/legalVersion';
import { LEGAL_REVISIONS } from '../../lib/legalHistory';

export default function TermsPage() {
  return (
    <div className="min-h-screen bg-stone-950 text-stone-200 flex flex-col font-sans selection:bg-amber-900 selection:text-amber-100">
      <LegalHeader
        title="서비스 이용약관"
        subtitle="마음지기 주역 AI 심층 성찰 상담 서비스 이용을 위한 기본 권리 및 의무 규정"
        badgeText={LEGAL_DOCUMENTS_VERSION}
      />

      <main className="flex-1 max-w-4xl w-full mx-auto px-4 py-8 sm:px-6 space-y-8 text-sm leading-relaxed">
        {/* 제1조 목적 */}
        <section className="space-y-3">
          <h2 className="text-base font-semibold text-stone-100 flex items-center gap-2 border-b border-stone-800 pb-2">
            <BookOpen className="w-4 h-4 text-amber-500" />
            제1조 (목적)
          </h2>
          <p className="text-stone-300">
            본 약관은 리인베스트먼트(대표자: 이승준, 이하 &apos;회사&apos;)가 운영하는 주역 기반 AI 심층 성찰 상담 서비스 &apos;마음지기&apos;(이하 &apos;서비스&apos;)의 이용과 관련하여, 회사와 이용자의 권리, 의무 및 책임사항, 기타 필요한 사항을 규정함을 목적으로 합니다.
          </p>
        </section>

        {/* 제2조 서비스의 성격 및 의료 면책 */}
        <section className="space-y-3">
          <h2 className="text-base font-semibold text-stone-100 flex items-center gap-2 border-b border-stone-800 pb-2">
            <ShieldAlert className="w-4 h-4 text-amber-500" />
            제2조 (서비스의 성격 및 한계)
          </h2>
          <div className="space-y-2 text-stone-300">
            <p>
              1. 본 서비스는 고전 주역(周易)의 철학적 지혜를 인공지능 기술로 재구성하여 이용자의 자기성찰과 의사결정 고민을 보조하는 <strong>개인용 웰니스(Wellness) 및 철학적 성찰 도구</strong>입니다.
            </p>
            <p>
              2. 본 서비스는 의료법, 정신건강증진 및 정신질환자 복지서비스 지원에 관한 법률상 <strong>의료행위, 정신과적 진단, 심리치료, 임상적 상담을 대체할 수 없으며</strong>, 법률·세무·투자 등 전문 자문을 제공하지 않습니다.
            </p>
            <p>
              3. 인공지능이 제시하는 괘의 해석과 조언은 미래에 대한 절대적 예언이나 확정적 사실이 아니며, 이용자는 자신의 자율적 판단과 책임하에 서비스 결과를 참고하여야 합니다.
            </p>
          </div>
        </section>

        {/* 제3조 이용 자격 및 연령 */}
        <section className="space-y-3">
          <h2 className="text-base font-semibold text-stone-100 flex items-center gap-2 border-b border-stone-800 pb-2">
            <CheckCircle className="w-4 h-4 text-amber-500" />
            제3조 (이용 자격 및 연령 제한)
          </h2>
          <div className="space-y-2 text-stone-300">
            <p>
              1. 심도 있는 자기성찰과 서비스 이용 책임성을 위하여, 본 서비스는 <strong>만 19세 이상의 성인</strong>을 주 이용 대상으로 합니다. 만 14세 미만 아동의 경우 가입 및 이용이 제한됩니다.
            </p>
            <p className="text-xs text-amber-300/90 bg-amber-500/10 p-2.5 rounded-lg border border-amber-500/20">
              ※ 로그인 및 가입 시 제공되는 만 19세 이상 확인 체크박스는 서비스 이용 자격 확인을 위한 자율적 이용자 확인 절차이며, 주민등록번호 등을 통한 본인확인기관의 법적 본인확인 절차를 대체하지 않습니다.
            </p>
          </div>
        </section>

        {/* 제4조 서비스 이용 및 크레딧 */}
        <section className="space-y-3">
          <h2 className="text-base font-semibold text-stone-100 flex items-center gap-2 border-b border-stone-800 pb-2">
            <CheckCircle className="w-4 h-4 text-amber-500" />
            제4조 (서비스 이용 및 크레딧)
          </h2>
          <div className="space-y-2 text-stone-300">
            <p>
              1. <strong>무료 베타 운영:</strong> 서비스는 현재 무료 베타 단계로 유료 결제 없이 신규 가입 시 제공되는 웰컴 크레딧(50 크레딧, 대화 5회분)으로 서비스를 이용하실 수 있습니다.
            </p>
            <p>
              2. <strong>크레딧 차감 기준 (대화 1회당 10 크레딧):</strong>
              <br />
              • 최초 질문 입력 및 괘 도출(본괘·지괘 산출 및 1차 AI 성찰 답변): <strong>10 크레딧</strong> 차감
              <br />
              • 이후 상담을 심화해 나가는 1:1 대화(채팅 턴 1회당): <strong>10 크레딧</strong> 차감
              <br />
              • 상담 종료 후 성찰 저널 요약 및 회고 카드 발급: 추가 차감 없음 (0 크레딧)
            </p>
            <p>
              3. <strong>심리 위기 안심 미차감:</strong> 심리적 위기 감지(BLOCK_CRISIS) 시 즉시 상담을 긴급 전문 지원 안내로 안전 전환하고 크레딧을 차감하지 않습니다(자동 환불 및 미차감 보장).
            </p>
          </div>
        </section>

        {/* 제5조 청약철회 및 환불 */}
        <section className="space-y-3">
          <h2 className="text-base font-semibold text-stone-100 flex items-center gap-2 border-b border-stone-800 pb-2">
            <CheckCircle className="w-4 h-4 text-amber-500" />
            제5조 (청약철회 및 환불)
          </h2>
          <p className="text-stone-300">
            현재는 유료 상품을 판매하지 않는 무료 베타 단계이며, 향후 정식 유료화 시 전자상거래법 등 관계 법령에 따라 공정한 환불 정책을 적용합니다. 세부 사항은 <Link href="/refund" className="text-amber-400 underline">환불 정책</Link>을 따릅니다.
          </p>
        </section>

        {/* 제6조 개인정보 처리 및 국외 이전 고지 안내 */}
        <section className="space-y-3">
          <h2 className="text-base font-semibold text-stone-100 flex items-center gap-2 border-b border-stone-800 pb-2">
            <CheckCircle className="w-4 h-4 text-amber-500" />
            제6조 (개인정보 처리 및 국외 이전 고지)
          </h2>
          <p className="text-stone-300 leading-relaxed">
            서비스의 안정적 제공 및 AI 성찰 추론(Google Cloud Vertex AI 등)을 위하여 개인정보가 국외로 이전(처리위탁 및 보관)될 수 있습니다. 국외로 이전되는 개인정보 항목, 수탁사, 국가, 이용 목적 및 거부 권리에 관한 구체적인 법정 고지 사항은{' '}
            <Link href="/privacy#cross-border" className="text-amber-400 underline font-medium">
              개인정보처리방침 제4절(개인정보의 국외 이전 고지)
            </Link>
            에서 확인하실 수 있습니다.
          </p>
        </section>

        {/* 제7조 책임의 한계 */}
        <section className="space-y-3">
          <h2 className="text-base font-semibold text-stone-100 flex items-center gap-2 border-b border-stone-800 pb-2">
            <ShieldAlert className="w-4 h-4 text-amber-500" />
            제7조 (책임의 한계)
          </h2>
          <p className="text-stone-300">
            회사는 천재지변, 외부 AI 모델 인프라 장애 등 불가항력적인 사유로 서비스가 일시 중단되는 경우 법률상 허용되는 한도 내에서 책임을 면합니다. 서비스의 결과물은 이용자의 주체적 결정을 돕기 위한 철학적 참고 자료이며, 최종 선택과 행동의 책임은 이용자 본인에게 있습니다.
          </p>
        </section>

        {/* 제8조 약관의 개정 및 이력 */}
        <section className="space-y-3">
          <h2 className="text-base font-semibold text-stone-100 flex items-center gap-2 border-b border-stone-800 pb-2">
            <BookOpen className="w-4 h-4 text-amber-500" />
            제8조 (약관의 개정 및 이력)
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse border border-stone-800 text-xs text-stone-400">
              <thead>
                <tr className="bg-stone-900 text-stone-300">
                  <th className="p-2.5 border border-stone-800 w-28">버전</th>
                  <th className="p-2.5 border border-stone-800 w-32">시행일</th>
                  <th className="p-2.5 border border-stone-800">주요 개정 내용</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-stone-800">
                {LEGAL_REVISIONS.map((item) => (
                  <tr key={item.version} className="hover:bg-stone-900/30">
                    <td className="p-2.5 font-medium text-stone-200 border border-stone-800">{item.version}</td>
                    <td className="p-2.5 text-stone-400 border border-stone-800">{item.effectiveDate}</td>
                    <td className="p-2.5 text-stone-300 border border-stone-800">
                      <div className="font-medium text-stone-200">{item.summary}</div>
                      <ul className="list-disc pl-4 mt-1 space-y-0.5 text-[11px] text-stone-400">
                        {item.changes.map((c, i) => (
                          <li key={i}>{c}</li>
                        ))}
                      </ul>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </main>

      <Footer />
    </div>
  );
}
