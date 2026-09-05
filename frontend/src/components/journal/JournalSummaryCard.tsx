'use client';

import React, { useState } from 'react';
import { motion } from 'framer-motion';
import {
  AlertTriangle,
  Calendar,
  CheckCircle2,
  Download,
  ExternalLink,
  HeartHandshake,
  RotateCcw,
  Sparkles,
  Target,
} from 'lucide-react';
import { JournalSummary } from '../../types/iching';
import { exportCardImageApi } from '../../lib/api';
import { renderCardCanvas } from '../../lib/cardCanvasRenderer';
import { ActionCardModal } from './ActionCardModal';

interface JournalSummaryCardProps {
  journal: JournalSummary;
  onRestart: () => void;
  className?: string;
}

export const JournalSummaryCard: React.FC<JournalSummaryCardProps> = ({
  journal,
  onRestart,
  className = '',
}) => {
  const isCrisis = Boolean(journal.isCrisis);
  const [isDownloaded, setIsDownloaded] = useState(false);
  const [previewImageUrl, setPreviewImageUrl] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [isServerDownloading, setIsServerDownloading] = useState(false);

  // 서버 사이드 고화질 EXIF 세척 이미지 다운로드 (모바일 인앱 브라우저 호환)
  const handleServerDownload = async () => {
    if (isServerDownloading) return;
    setIsServerDownloading(true);
    try {
      const cardPayload = journal.cardData || {
        is_crisis: isCrisis,
        universe_transition: journal.clarifiedQuestion,
        sacred_metaphor: journal.hexagramSummary,
        client_aha_moment: (journal.keyInsights || []).join('\n'),
        client_action_pledge: journal.suggestedAction,
        counselor_reframing: '당신의 고결한 뜻과 실천을 온 마음으로 응원합니다.',
      };
      const blob = await exportCardImageApi(cardPayload);
      const blobUrl = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.style.display = 'none';
      link.download = `마음전념카드_서버원본_${new Date().toISOString().slice(0, 10)}.png`;
      link.href = blobUrl;
      document.body.appendChild(link);
      link.click();
      setTimeout(() => {
        if (document.body.contains(link)) document.body.removeChild(link);
        URL.revokeObjectURL(blobUrl);
      }, 1500);
      setIsDownloaded(true);
      setTimeout(() => setIsDownloaded(false), 3000);
    } catch (err) {
      console.error('서버 카드 다운로드 오류:', err);
      alert('서버 이미지 생성 중 문제가 발생했습니다. 브라우저 저장 기능을 이용해 주세요.');
    } finally {
      setIsServerDownloading(false);
    }
  };

  // 클라이언트 Canvas 렌더링 및 다운로드 (실패 시 서버 다운로드 자동 폴백)
  const generateAndDownloadCard = () => {
    try {
      const { dataUrl, blob, fileName } = renderCardCanvas(journal);
      setPreviewImageUrl(dataUrl);

      // 동기식 Blob 다운로드 링크 트리거
      const blobUrl = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.style.display = 'none';
      link.download = fileName;
      link.href = blobUrl;
      document.body.appendChild(link);
      link.click();

      setTimeout(() => {
        if (document.body.contains(link)) document.body.removeChild(link);
        URL.revokeObjectURL(blobUrl);
      }, 1500);

      setIsDownloaded(true);
      setTimeout(() => setIsDownloaded(false), 3000);
    } catch (err) {
      console.error('클라이언트 카드 생성 오류, 서버 다운로드로 자동 폴백:', err);
      handleServerDownload();
    }
  };

  // 클립보드에 이미지 복사
  const handleCopyImage = async () => {
    if (!previewImageUrl) return;
    try {
      const res = await fetch(previewImageUrl);
      const blob = await res.blob();
      await navigator.clipboard.write([
        new ClipboardItem({ 'image/png': blob }),
      ]);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('클립보드 복사 실패:', err);
    }
  };

  // 로컬 파일 재다운로드 핸들러
  const handleLocalDownload = async () => {
    if (!previewImageUrl) return;
    try {
      const res = await fetch(previewImageUrl);
      const blob = await res.blob();
      const blobUrl = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.style.display = 'none';
      link.download = `마음전념카드_${new Date().toISOString().slice(0, 10)}.png`;
      link.href = blobUrl;
      document.body.appendChild(link);
      link.click();
      setTimeout(() => {
        if (document.body.contains(link)) document.body.removeChild(link);
        URL.revokeObjectURL(blobUrl);
      }, 1500);
    } catch {
      const link = document.createElement('a');
      link.download = `마음전념카드_${new Date().toISOString().slice(0, 10)}.png`;
      link.href = previewImageUrl;
      document.body.appendChild(link);
      link.click();
      setTimeout(() => {
        if (document.body.contains(link)) document.body.removeChild(link);
      }, 500);
    }
  };

  return (
    <>
      <div className={`w-full max-w-2xl mx-auto space-y-6 ${className}`}>
        {/* 상단 카드 헤더 */}
        <motion.div
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          className={`p-6 rounded-2xl border transition-all ${
            isCrisis
              ? 'bg-rose-950/40 border-rose-800/80 shadow-rose-950/20'
              : 'bg-stone-900/60 border-stone-800 shadow-stone-950/30'
          } shadow-xl backdrop-blur-md`}
        >
          <div className="flex items-center justify-between border-b border-stone-800/80 pb-4 mb-5">
            <div className="flex items-center gap-2.5">
              <div
                className={`p-2 rounded-lg ${
                  isCrisis ? 'bg-rose-900/50 text-rose-400' : 'bg-amber-950/60 text-amber-400'
                }`}
              >
                {isCrisis ? <AlertTriangle className="w-5 h-5" /> : <Sparkles className="w-5 h-5" />}
              </div>
              <div>
                <h3 className="text-base font-semibold text-stone-100">
                  {isCrisis ? '긴급 마음 안심 카드' : '마음 전념 카드'}
                </h3>
                <p className="text-xs text-stone-400">
                  {isCrisis
                    ? '생명과 안정을 지키는 Stanley-Brown 안전계획'
                    : '지행합일(知行合一) : 성찰을 일상의 실천으로'}
                </p>
              </div>
            </div>

            {journal.createdAt && (
              <div className="flex items-center gap-1.5 text-xs text-stone-500 bg-stone-950/40 px-2.5 py-1 rounded-full border border-stone-800/60">
                <Calendar className="w-3.5 h-3.5" />
                <span>{journal.createdAt}</span>
              </div>
            )}
          </div>

          {/* 질문 및 괘 요약 */}
          <div className="space-y-4 text-sm">
            <div>
              <span className="text-xs font-semibold text-stone-400 uppercase tracking-wider block mb-1">
                성찰의 출발점
              </span>
              <p className="text-stone-200 leading-relaxed bg-stone-950/40 p-3.5 rounded-xl border border-stone-800/40">
                {journal.clarifiedQuestion}
              </p>
            </div>

            <div>
              <span className="text-xs font-semibold text-stone-400 uppercase tracking-wider block mb-1">
                성찰을 비추는 괘
              </span>
              <p className="text-stone-300 bg-stone-950/40 p-3 rounded-xl border border-stone-800/40">
                {journal.hexagramSummary}
              </p>
            </div>

            {/* 핵심 통찰 */}
            {journal.keyInsights && journal.keyInsights.length > 0 && (
              <div>
                <span className="text-xs font-semibold text-stone-400 uppercase tracking-wider block mb-1">
                  깊이 새겨둘 통찰
                </span>
                <ul className="space-y-2 bg-stone-950/40 p-3.5 rounded-xl border border-stone-800/40">
                  {journal.keyInsights.map((insight, idx) => (
                    <li key={idx} className="text-stone-300 flex items-start gap-2 text-xs leading-relaxed">
                      <span className="text-amber-500 font-bold mt-0.5">•</span>
                      <span>{insight}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* 오늘 나의 전념 행동 */}
            {journal.suggestedAction && (
              <div className="pt-1">
                <div
                  className={`p-4 rounded-xl border ${
                    isCrisis
                      ? 'bg-rose-900/30 border-rose-700/60 text-rose-100'
                      : 'bg-amber-950/30 border-amber-800/60 text-amber-100'
                  }`}
                >
                  <div className="flex items-center gap-2 mb-2 font-medium text-xs">
                    <Target className={`w-4 h-4 ${isCrisis ? 'text-rose-400' : 'text-amber-400'}`} />
                    <span>오늘 나의 전념 행동 (行)</span>
                  </div>
                  <p className="text-xs leading-relaxed font-normal whitespace-pre-wrap">
                    {journal.suggestedAction}
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* 액션 버튼 */}
          <div className="mt-6 pt-4 border-t border-stone-800/80 flex flex-wrap gap-2.5">
            <button
              onClick={generateAndDownloadCard}
              className="flex-1 min-w-[140px] py-2.5 px-4 rounded-xl bg-gradient-to-r from-amber-600 to-amber-500 hover:from-amber-500 hover:to-amber-400 text-stone-950 font-semibold text-xs flex items-center justify-center gap-2 shadow-lg shadow-amber-950/30 transition-all cursor-pointer"
            >
              {isDownloaded ? (
                <>
                  <CheckCircle2 className="w-4 h-4 text-emerald-950" />
                  <span>카드 저장 완료!</span>
                </>
              ) : (
                <>
                  <Download className="w-4 h-4" />
                  <span>마음 전념 카드 소장</span>
                </>
              )}
            </button>

            <button
              onClick={onRestart}
              className="py-2.5 px-4 rounded-xl bg-stone-800/80 hover:bg-stone-700/80 text-stone-300 text-xs flex items-center justify-center gap-1.5 border border-stone-700/60 transition-all cursor-pointer"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>새로운 상담</span>
            </button>
          </div>
        </motion.div>
      </div>

      {/* 인앱 뷰어 모달 (서브 컴포넌트) */}
      <ActionCardModal
        isOpen={Boolean(previewImageUrl)}
        imageUrl={previewImageUrl}
        isServerDownloading={isServerDownloading}
        copied={copied}
        onClose={() => setPreviewImageUrl(null)}
        onDownloadLocal={handleLocalDownload}
        onDownloadServer={handleServerDownload}
        onCopyImage={handleCopyImage}
      />
    </>
  );
};
