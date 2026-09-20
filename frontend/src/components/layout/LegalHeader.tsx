import React from 'react';
import Link from 'next/link';
import { ArrowLeft, FileText } from 'lucide-react';

interface LegalHeaderProps {
  title: string;
  subtitle: string;
  badgeText?: string;
  lastUpdated?: string;
}

export const LegalHeader: React.FC<LegalHeaderProps> = ({
  title,
  subtitle,
  badgeText = 'v2026-09-19 (공식 고지)',
  lastUpdated = '2026년 9월 19일',
}) => {
  return (
    <header className="border-b border-stone-800/80 bg-stone-900/50 backdrop-blur-md sticky top-0 z-40">
      <div className="max-w-4xl mx-auto px-4 py-4 sm:px-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 text-xs text-amber-500/90 hover:text-amber-400 transition font-medium mb-1.5"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>마음지기 홈으로 돌아가기</span>
          </Link>
          <div className="flex items-center gap-2.5">
            <h1 className="text-lg sm:text-xl font-medium text-stone-100 tracking-tight flex items-center gap-2">
              <FileText className="w-4 h-4 text-amber-500/80" />
              {title}
            </h1>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-medium bg-amber-500/10 text-amber-400 border border-amber-500/30">
              {badgeText}
            </span>
          </div>
          <p className="text-xs text-stone-400 mt-0.5">{subtitle}</p>
        </div>
        <div className="text-[11px] text-stone-400 font-mono self-start sm:self-auto">
          최종 개정일: {lastUpdated}
        </div>
      </div>
    </header>
  );
};
