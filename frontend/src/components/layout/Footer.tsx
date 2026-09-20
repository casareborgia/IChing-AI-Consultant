import React from 'react';
import Link from 'next/link';
import { AlertCircle, Sparkles, Scale } from 'lucide-react';

export const Footer: React.FC = () => {
  return (
    <footer className="border-t border-stone-800/80 bg-stone-950/95 py-12 px-4 sm:px-6 lg:px-8 text-xs text-stone-400 font-light leading-relaxed">
      <div className="max-w-5xl mx-auto space-y-8">
        {/* 1. 상단: 웰니스 & AI 서비스 성격 고지 (AI 기본법 취지 반영 및 면책) */}
        <div className="p-4 rounded-xl bg-stone-900/70 border border-stone-800/80 text-[12px] space-y-2 text-left">
          <div className="flex items-center gap-2 text-amber-400/90 font-medium">
            <Sparkles className="w-4 h-4 shrink-0" />
            <span>생성형 AI 기반 자기성찰 서비스 고지 (AI 기본법 가이드라인 준수)</span>
          </div>
          <p className="text-stone-400 leading-relaxed">
            본 서비스는 주역(周易)의 고전 철학을 바탕으로 이용자의 자기성찰과 내면 탐색을 돕는 <strong className="text-stone-300">인공지능 기반 웰니스 도구</strong>입니다.
            의학적·정신과적 진단이나 치료, 전문 법률·금융 자문을 제공하지 않으며, 점단 결과나 미래의 확정적 예측을 보장하지 않습니다.
          </p>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-stone-300 pt-1 border-t border-stone-800/50">
            <span className="flex items-center gap-1 text-rose-400 font-medium">
              <AlertCircle className="w-3.5 h-3.5" /> 긴급 위기 상담:
            </span>
            <span>급박한 심리적 위기나 자해·자살 충동이 있을 경우 즉시</span>
            <a
              href="tel:109"
              className="text-amber-300 font-semibold underline hover:text-amber-200 transition"
              title="24시간 자살예방 상담전화"
            >
              109 (24시간 무상)
            </a>
            <span>또는</span>
            <a
              href="tel:1577-0199"
              className="text-amber-300 font-semibold underline hover:text-amber-200 transition"
              title="정신건강상담전화"
            >
              1577-0199
            </a>
            <span>로 연락하여 전문 의료진의 도움을 받으시기 바랍니다.</span>
          </div>
        </div>

        {/* 2. 중단: 8대 정책 및 안내 내비게이션 링크 */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 py-2 text-[12px] border-y border-stone-800/60">
          <div className="space-y-2">
            <h4 className="text-stone-300 font-medium tracking-wide">서비스 약관</h4>
            <ul className="space-y-1.5">
              <li>
                <Link href="/terms" className="hover:text-amber-400 transition inline-flex items-center gap-1">
                  이용약관
                </Link>
              </li>
              <li>
                <Link href="/pricing" className="hover:text-amber-400 transition inline-flex items-center gap-1">
                  이용 요금 안내
                </Link>
              </li>
            </ul>
          </div>

          <div className="space-y-2">
            <h4 className="text-stone-300 font-medium tracking-wide">개인정보 & 보안</h4>
            <ul className="space-y-1.5">
              <li>
                <Link href="/privacy" className="hover:text-amber-400 transition font-medium text-stone-300 inline-flex items-center gap-1">
                  개인정보처리방침
                </Link>
              </li>
              <li>
                <Link href="/refund" className="hover:text-amber-400 transition inline-flex items-center gap-1">
                  환불 및 청약철회
                </Link>
              </li>
            </ul>
          </div>

          <div className="space-y-2">
            <h4 className="text-stone-300 font-medium tracking-wide">안전 & 책임</h4>
            <ul className="space-y-1.5">
              <li>
                <Link href="/ai-notice" className="hover:text-amber-400 transition inline-flex items-center gap-1">
                  AI 투명성 고지
                </Link>
              </li>
              <li>
                <Link href="/safety" className="hover:text-amber-400 transition inline-flex items-center gap-1">
                  위기 대응 안내
                </Link>
              </li>
            </ul>
          </div>

          <div className="space-y-2">
            <h4 className="text-stone-300 font-medium tracking-wide">정보 & 지원</h4>
            <ul className="space-y-1.5">
              <li>
                <Link href="/licenses" className="hover:text-amber-400 transition inline-flex items-center gap-1">
                  오픈소스 & 라이선스
                </Link>
              </li>
              <li>
                <Link href="/contact" className="hover:text-amber-400 transition inline-flex items-center gap-1">
                  고객지원 및 문의
                </Link>
              </li>
            </ul>
          </div>
        </div>

        {/* 3. 하단: 사업자 정보 (D01 공식 고지) & 데이터 라이선스 */}
        <div className="space-y-3 text-[11px] text-stone-400 text-left sm:text-center">
          <div className="p-3 rounded-lg bg-stone-900/40 border border-stone-800/60 max-w-3xl mx-auto text-left space-y-1">
            <div className="flex items-center gap-1.5 text-stone-300 font-medium">
              <Scale className="w-3.5 h-3.5 text-amber-500" />
              <span>사업자 정보 및 서비스 운영 고지</span>
            </div>
            <p className="text-stone-400 leading-relaxed">
              서비스명: 마음지기 | 상호명: 리인베스트먼트 | 대표자: 이승준 | 사업자등록번호: 771-05-03690 | 사업장 소재지: 서울특별시 (상세 주소는 고객지원 문의) |
              고객문의: <a href="mailto:casareborgia@gmail.com" className="text-amber-400/90 underline">casareborgia@gmail.com</a> (<Link href="/contact" className="text-amber-400/90 underline">고객지원 센터</Link>) |
              개인정보보호책임자: 이승준
            </p>
            <p className="text-stone-500 text-[10px]">
              * 본 서비스는 무료 베타 운영 중이며 현재 유료 결제 상품을 판매하지 않습니다. (통신판매업 신고는 향후 정식 유료 결제 서비스 도입 시 완료될 예정입니다.)
            </p>
          </div>

          <div className="space-y-1 text-stone-400 pt-2">
            <p>
              📜 <span className="text-stone-300 font-medium">주역 원문 및 역사적 주석 출처:</span> 漢籍리포지토리(Kanseki Repository)
              KR1a0001(경문) · KR1a0016(이천역전) · KR1a0031(주역본의) (CC BY-SA 4.0), 교토대학 인문과학연구소 저본 기반.
            </p>
            <p>
              오픈소스 소프트웨어 라이선스: MIT License | 가공 데이터 및 번역 라이선스: Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)
            </p>
            <p className="text-stone-400">
              © 2026 마음지기 (리인베스트먼트). All rights reserved.
            </p>
          </div>
        </div>
      </div>
    </footer>
  );
};
