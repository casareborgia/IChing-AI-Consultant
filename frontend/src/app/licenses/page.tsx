import React from 'react';
import { LegalHeader } from '../../components/layout/LegalHeader';
import { Footer } from '../../components/layout/Footer';
import { BookMarked, Code, FileCode2 } from 'lucide-react';
import { LEGAL_DOCUMENTS_VERSION } from '../../lib/legalVersion';

export default function LicensesPage() {
  return (
    <div className="min-h-screen bg-stone-950 text-stone-200 flex flex-col font-sans selection:bg-amber-900 selection:text-amber-100">
      <LegalHeader
        title="오픈소스 및 데이터 라이선스"
        subtitle="고전 문헌 데이터 출처, 가공 저작권 및 오픈소스 소프트웨어 라이선스 고지"
        badgeText={LEGAL_DOCUMENTS_VERSION}
      />

      <main className="flex-1 max-w-4xl w-full mx-auto px-4 py-8 sm:px-6 space-y-8 text-sm leading-relaxed">
        {/* 1. 고전 데이터 출처 및 CC BY-SA 4.0 안내 */}
        <section className="space-y-3">
          <h2 className="text-base font-semibold text-stone-100 flex items-center gap-2 border-b border-stone-800 pb-2">
            <BookMarked className="w-4 h-4 text-amber-500" />
            1. 주역 고전 원문 및 역사적 주석 데이터 출처 (D13 라이선스 고지)
          </h2>
          <div className="space-y-2 text-stone-300">
            <p>
              본 서비스의 주역 64괘 386효 경문 및 송대 정전(程傳)·주자 본의(本義) 고전 주석은
              <strong>교토대학 인문과학연구소(Kyoto University Institute for Research in Humanities)</strong> 주관의
              <strong>漢籍리포지토리(Kanseki Repository)</strong> 디지털 표점본을 저본으로 합니다.
            </p>
            <div className="p-4 rounded-xl bg-stone-900/70 border border-stone-800 text-xs space-y-1.5 font-mono">
              <p>• KR1a0001: 《周易》 (경문 64괘 및 십익 원문)</p>
              <p>• KR1a0016: 程頤 《伊川易傳》 (이천역전 4권)</p>
              <p>• KR1a0031: 朱熹 《原本周易本義》 (문연각 사고전서본 주역본의 6권)</p>
            </div>
            <p className="text-xs text-stone-400">
              라이선스: <strong>Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)</strong><br />
              원저작자 표시, 출처 명시 및 동일조건변경허락에 따라 공유 및 활용됩니다.
            </p>
          </div>
        </section>

        {/* 2. 현대 한국어 번역 및 파생 데이터 라이선스 */}
        <section className="space-y-3">
          <h2 className="text-base font-semibold text-stone-100 flex items-center gap-2 border-b border-stone-800 pb-2">
            <FileCode2 className="w-4 h-4 text-amber-500" />
            2. 현대 한국어 번역 데이터 및 RAG 청크 라이선스
          </h2>
          <div className="space-y-2 text-stone-300">
            <p>
              Kanseki Repository 저본을 바탕으로 한자 원문 표점 교감 및 현대 한국어 풀이로 번역·가공된 주역 데이터베이스(2,536건 주석 청크 및 괘효사 번역문)는
              <strong>CC BY-SA 4.0</strong> 라이선스 조건을 계승합니다.
            </p>
            <p className="text-xs text-stone-400">
              * 동일한 라이선스(CC BY-SA 4.0) 조건을 준수하는 한, 누구든지 해당 번역 및 교감 가공 데이터를 공유·재배포할 수 있습니다.
            </p>
          </div>
        </section>

        {/* 3. 소프트웨어 코드 라이선스 (MIT License) */}
        <section className="space-y-3">
          <h2 className="text-base font-semibold text-stone-100 flex items-center gap-2 border-b border-stone-800 pb-2">
            <Code className="w-4 h-4 text-amber-500" />
            3. 애플리케이션 소프트웨어 라이선스 (MIT License)
          </h2>
          <div className="space-y-2 text-stone-300">
            <p>
              I-Ching AI Consultant의 파이프라인 엔진, 멀티에이전트 오케스트레이션 로직 및 프론트엔드 소프트웨어 코드는
              <strong>MIT License</strong>에 따라 공개되어 있습니다.
            </p>
            <div className="p-4 rounded-xl bg-stone-900/70 border border-stone-800 text-[11px] font-mono text-stone-400 space-y-1">
              <p>Copyright (c) 2026 I-Ching AI Consultant Project Contributors</p>
              <p className="pt-1">
                Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the &quot;Software&quot;), to deal in the Software without restriction...
              </p>
            </div>
          </div>
        </section>
      </main>

      <Footer />
    </div>
  );
}
