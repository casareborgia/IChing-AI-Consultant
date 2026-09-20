'use client';

import React, { useState } from 'react';
import { motion } from 'framer-motion';
import {
  AlertTriangle,
  Calendar,
  CheckCircle2,
  Download,
  RotateCcw,
  Sparkles,
  Target,
  Trash2,
} from 'lucide-react';
import { JournalSummary } from '../../types/iching';
import { exportCardImageApi, deleteRecordApi } from '../../lib/api';
import { renderCardCanvas } from '../../lib/cardCanvasRenderer';
import { ActionCardModal } from './ActionCardModal';

interface JournalSummaryCardProps {
  journal: JournalSummary;
  onRestart: () => void;
  sessionId?: string;
  className?: string;
}

export const JournalSummaryCard: React.FC<JournalSummaryCardProps> = ({
  journal,
  onRestart,
  sessionId,
  className = '',
}) => {
  const isCrisis = Boolean(journal.isCrisis);
  const [isDownloaded, setIsDownloaded] = useState(false);
  const [previewImageUrl, setPreviewImageUrl] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [isServerDownloading, setIsServerDownloading] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const handleDeleteRecord = async () => {
    if (!sessionId || isDeleting) return;
    setIsDeleting(true);
    try {
      await deleteRecordApi(sessionId);
      alert('상담 대화록 및 성찰 저널이 즉시 완전히 삭제되었습니다.');
      setIsDeleteModalOpen(false);
      onRestart();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : '상담 기록 삭제 중 오류가 발생했습니다.';
      alert(message);
    } finally {
      setIsDeleting(false);
    }
  };

  // 서버 사이드 고화질 EXIF 세척 이미지 다운로드 (모바일 인앱 브라우저 호환, BLK-C08-01)
  const handleServerDownload = async () => {
    if (isServerDownloading) return;
    if (!sessionId) {
      alert('세션 정보를 찾을 수 없습니다. 브라우저 저장 기능을 이용해 주세요.');
      return;
    }
    setIsServerDownloading(true);
    try {
      const blob = await exportCardImageApi(sessionId);
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
      alert('서버 저장 카드를 불러오는 데 실패했습니다. 브라우저 저장 기능을 이용해 주세요.');
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

            {sessionId && (
              <button
                onClick={() => setIsDeleteModalOpen(true)}
                className="py-2.5 px-3.5 rounded-xl bg-stone-900/60 hover:bg-rose-950/40 text-stone-400 hover:text-rose-300 text-xs flex items-center justify-center gap-1.5 border border-stone-800 hover:border-rose-800/60 transition-all cursor-pointer"
                title="상담 기록 영구 삭제"
              >
                <Trash2 className="w-3.5 h-3.5" />
                <span>이 상담 기록 삭제</span>
              </button>
            )}
          </div>
        </motion.div>
      </div>

      {/* 상담 기록 영구 삭제 확인 모달 */}
      {isDeleteModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-stone-950/80 backdrop-blur-sm">
          <div className="w-full max-w-sm rounded-2xl border border-rose-900/60 bg-stone-900 p-6 shadow-2xl text-stone-200">
            <h4 className="font-semibold text-rose-400 text-base flex items-center gap-2">
              <Trash2 className="w-4 h-4 text-rose-400" />
              상담 기록 영구 삭제
            </h4>
            <p className="mt-3 text-xs leading-relaxed text-stone-300">
              이 상담의 대화 내용 및 성찰 저널을 완전히 삭제하시겠습니까?
            </p>
            <p className="mt-2 text-[11px] leading-relaxed text-rose-300/80 bg-rose-950/30 p-2.5 rounded-lg border border-rose-900/40">
              삭제된 기록은 즉시 영구 파기되며 다시 복구할 수 없습니다 (원장의 크레딧 차감 내역은 보존되나 상담 본문은 완전 삭제됩니다).
            </p>
            <div className="mt-5 flex gap-2 justify-end">
              <button
                onClick={() => setIsDeleteModalOpen(false)}
                disabled={isDeleting}
                className="px-3.5 py-2 text-xs rounded-xl bg-stone-800 hover:bg-stone-700 text-stone-300 transition"
              >
                취소
              </button>
              <button
                onClick={handleDeleteRecord}
                disabled={isDeleting}
                className="px-3.5 py-2 text-xs rounded-xl bg-rose-700 hover:bg-rose-600 text-white font-medium transition flex items-center gap-1.5"
              >
                {isDeleting ? '삭제 중...' : '영구 삭제'}
              </button>
            </div>
          </div>
        </div>
      )}

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
