import React, { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, BookOpen, Clock, MessageSquare, Sparkles, ChevronRight, ArrowLeft, Trash2, RefreshCw, MessageCircle } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import {
  fetchMyRecordsApi,
  fetchRecordDetailApi,
  deleteRecordApi,
  ConsultationRecordItem,
  ConsultationRecordDetail,
} from '@/lib/api';

interface ConsultationHistoryModalProps {
  isOpen: boolean;
  onClose: () => void;
  onResumeSession?: (record: ConsultationRecordDetail) => void;
}

export const ConsultationHistoryModal: React.FC<ConsultationHistoryModalProps> = ({ isOpen, onClose, onResumeSession }) => {
  const { profile } = useAuth();
  const [records, setRecords] = useState<ConsultationRecordItem[]>([]);
  const [isLoadingList, setIsLoadingList] = useState<boolean>(true);
  const [listError, setListError] = useState<string | null>(null);

  // 상세 뷰 상태
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [detailData, setDetailData] = useState<ConsultationRecordDetail | null>(null);
  const [isLoadingDetail, setIsLoadingDetail] = useState<boolean>(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [detailTab, setDetailTab] = useState<'journal' | 'turns'>('journal');
  const [isDeleting, setIsDeleting] = useState<boolean>(false);

  const loadRecords = useCallback(async () => {
    setIsLoadingList(true);
    setListError(null);
    try {
      const res = await fetchMyRecordsApi(30);
      setRecords(res.records || []);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '기록을 불러오지 못했습니다.';
      setListError(msg);
    } finally {
      setIsLoadingList(false);
    }
  }, []);

  useEffect(() => {
    if (isOpen) {
      loadRecords();
      setSelectedSessionId(null);
      setDetailData(null);
    }
  }, [isOpen, loadRecords]);

  const handleSelectRecord = async (sessionId: string) => {
    setSelectedSessionId(sessionId);
    setIsLoadingDetail(true);
    setDetailError(null);
    try {
      const detail = await fetchRecordDetailApi(sessionId);
      setDetailData(detail);
      // 저널이 있으면 저널 탭을 기본으로, 없으면 대화 탭으로
      setDetailTab(detail.journal ? 'journal' : 'turns');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '상세 기록을 불러오지 못했습니다.';
      setDetailError(msg);
    } finally {
      setIsLoadingDetail(false);
    }
  };

  const handleDeleteRecord = async (sessionId: string) => {
    if (!window.confirm('이 상담 기록과 대화, 성찰 저널을 영구적으로 삭제하시겠습니까? (복구할 수 없습니다)')) {
      return;
    }
    setIsDeleting(true);
    try {
      await deleteRecordApi(sessionId);
      alert('상담 기록이 삭제되었습니다.');
      setSelectedSessionId(null);
      setDetailData(null);
      loadRecords();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '삭제에 실패했습니다.';
      alert(msg);
    } finally {
      setIsDeleting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4">
        {/* Backdrop */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
          className="absolute inset-0 bg-stone-950/80 backdrop-blur-md"
        />

        {/* Modal Window */}
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 15 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 15 }}
          className="relative w-full max-w-2xl max-h-[85vh] flex flex-col overflow-hidden rounded-3xl border border-stone-800 bg-stone-900 shadow-2xl text-stone-200"
        >
          {/* Header */}
          <div className="flex items-center justify-between border-b border-stone-800/80 px-5 py-4 bg-stone-900/90">
            <div className="flex items-center gap-2.5">
              {selectedSessionId ? (
                <button
                  onClick={() => {
                    setSelectedSessionId(null);
                    setDetailData(null);
                  }}
                  className="p-1 rounded-lg text-stone-400 hover:text-stone-100 hover:bg-stone-800 transition cursor-pointer"
                  title="목록으로 돌아가기"
                >
                  <ArrowLeft className="w-5 h-5" />
                </button>
              ) : (
                <div className="w-8 h-8 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400">
                  <BookOpen className="w-4 h-4" />
                </div>
              )}
              <div>
                <h3 className="text-base font-bold text-stone-100 font-serif">
                  {selectedSessionId ? '상담 및 성찰 저널 복습' : '내 상담 기록 보관함'}
                </h3>
                <p className="text-[11px] text-stone-400 font-light">
                  {selectedSessionId ? '과거에 도출된 괘와 삶의 통찰을 다시 돌아봅니다.' : '주역을 통해 나누었던 깊은 성찰의 여정'}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-1.5">
              {!selectedSessionId && (
                <button
                  onClick={loadRecords}
                  disabled={isLoadingList}
                  className="p-1.5 rounded-lg text-stone-400 hover:text-stone-200 hover:bg-stone-800 transition cursor-pointer disabled:opacity-50"
                  title="새로고침"
                >
                  <RefreshCw className={`w-4 h-4 ${isLoadingList ? 'animate-spin' : ''}`} />
                </button>
              )}
              <button
                onClick={onClose}
                className="p-1.5 rounded-lg text-stone-400 hover:text-stone-100 hover:bg-stone-800 transition cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
          </div>

          {/* Body Content */}
          <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4">
            {/* 1. 목록 뷰 */}
            {!selectedSessionId && (
              <>
                {isLoadingList && (
                  <div className="py-16 text-center text-stone-500 text-sm flex flex-col items-center gap-2">
                    <RefreshCw className="w-6 h-6 animate-spin text-amber-500/70" />
                    <span>상담 기록을 불러오는 중입니다...</span>
                  </div>
                )}

                {listError && (
                  <div className="p-4 rounded-xl bg-red-950/40 border border-red-800/60 text-xs text-red-300 text-center">
                    {listError}
                  </div>
                )}

                {!isLoadingList && !listError && records.length === 0 && (
                  <div className="py-16 text-center space-y-3">
                    <div className="w-12 h-12 mx-auto rounded-full bg-stone-800/80 border border-stone-700 flex items-center justify-center text-stone-400 text-xl">
                      📜
                    </div>
                    <p className="text-sm text-stone-300 font-medium">아직 저장된 상담 기록이 없습니다.</p>
                    <p className="text-xs text-stone-500 max-w-sm mx-auto">
                      마음속 고민을 털어놓고 괘를 뽑아 대화를 나누시면, 종료 시 여기에 영구 보관되어 언제든 다시 복습할 수 있습니다.
                    </p>
                  </div>
                )}

                {!isLoadingList && records.length > 0 && (
                  <div className="space-y-3">
                    {records.map((rec) => {
                      const hexTitle = rec.report_data?.hexagram_casting?.original_name_full
                        ? `${rec.report_data.hexagram_casting.original_hex_id}. ${rec.report_data.hexagram_casting.original_name_full}`
                        : (rec.original_hexagram_id ? `제${rec.original_hexagram_id}괘` : null);
                      const formattedDate = rec.created_at
                        ? new Date(rec.created_at).toLocaleDateString('ko-KR', {
                            year: 'numeric',
                            month: 'long',
                            day: 'numeric',
                            hour: '2-digit',
                            minute: '2-digit',
                          })
                        : '';

                      return (
                        <div
                          key={rec.session_id}
                          onClick={() => handleSelectRecord(rec.session_id)}
                          className="group p-4 rounded-2xl border border-stone-800 bg-stone-950/60 hover:bg-stone-800/40 hover:border-amber-500/40 transition-all cursor-pointer flex items-center justify-between gap-3"
                        >
                          <div className="space-y-1.5 flex-1 min-w-0">
                            <div className="flex items-center gap-2 flex-wrap text-[11px]">
                              {hexTitle && (
                                <span className="px-2 py-0.5 rounded-md bg-amber-500/10 text-amber-300 border border-amber-500/20 font-medium">
                                  {hexTitle}
                                </span>
                              )}
                              {rec.has_journal && (
                                <span className="px-2 py-0.5 rounded-md bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-1 font-medium">
                                  <Sparkles className="w-3 h-3" />
                                  <span>성찰 저널 완주</span>
                                </span>
                              )}
                              <span className="text-stone-500 flex items-center gap-1">
                                <Clock className="w-3 h-3" />
                                {formattedDate}
                              </span>
                              <span className="text-stone-500 flex items-center gap-1">
                                <MessageSquare className="w-3 h-3" />
                                {rec.turn_count}턴
                              </span>
                            </div>
                            <h4 className="text-sm font-medium text-stone-100 truncate group-hover:text-amber-200 transition">
                              {rec.raw_question}
                            </h4>
                          </div>

                          <ChevronRight className="w-5 h-5 text-stone-600 group-hover:text-amber-400 transition shrink-0" />
                        </div>
                      );
                    })}
                  </div>
                )}
              </>
            )}

            {/* 2. 상세 뷰 */}
            {selectedSessionId && (
              <>
                {isLoadingDetail && (
                  <div className="py-16 text-center text-stone-500 text-sm flex flex-col items-center gap-2">
                    <RefreshCw className="w-6 h-6 animate-spin text-amber-500/70" />
                    <span>상담 기록과 저널을 불러오고 있습니다...</span>
                  </div>
                )}

                {detailError && (
                  <div className="p-4 rounded-xl bg-red-950/40 border border-red-800/60 text-xs text-red-300 text-center">
                    {detailError}
                  </div>
                )}

                {!isLoadingDetail && detailData && (
                  <div className="space-y-4">
                    {/* 질문 및 괘 요약 카드 */}
                    <div className="p-4 rounded-2xl bg-stone-950/70 border border-stone-800 space-y-2">
                      <span className="text-[11px] font-semibold text-amber-400 tracking-wider uppercase block">
                        당시 마음에 품었던 질문
                      </span>
                      <p className="text-sm text-stone-100 font-serif leading-relaxed">
                        &ldquo;{detailData.raw_question}&rdquo;
                      </p>
                      {detailData.report_data?.hexagram_casting && (
                        <div className="pt-2 border-t border-stone-800/80 flex items-center gap-3 text-xs text-stone-400">
                          <span className="text-amber-300 font-medium">
                            도출 괘: {detailData.report_data.hexagram_casting.original_hex_id}. {detailData.report_data.hexagram_casting.original_name_full} ({detailData.report_data.hexagram_casting.original_name_hanja})
                          </span>
                          {detailData.report_data.hexagram_casting.original_summary && (
                            <span className="text-stone-500 truncate">
                              상징: {detailData.report_data.hexagram_casting.original_summary}
                            </span>
                          )}
                        </div>
                      )}
                    </div>

                    {/* 탭 전환 */}
                    <div className="flex border-b border-stone-800 text-xs">
                      <button
                        onClick={() => setDetailTab('journal')}
                        className={`pb-2.5 px-4 font-medium transition cursor-pointer ${
                          detailTab === 'journal'
                            ? 'text-amber-400 border-b-2 border-amber-400'
                            : 'text-stone-400 hover:text-stone-200'
                        }`}
                      >
                        📜 성찰 저널 요약 {detailData.journal ? '' : '(미작성)'}
                      </button>
                      <button
                        onClick={() => setDetailTab('turns')}
                        className={`pb-2.5 px-4 font-medium transition cursor-pointer ${
                          detailTab === 'turns'
                            ? 'text-amber-400 border-b-2 border-amber-400'
                            : 'text-stone-400 hover:text-stone-200'
                        }`}
                      >
                        💬 나눈 대화 기록 ({detailData.turns.length})
                      </button>
                    </div>

                    {/* 저널 탭 내용 */}
                    {detailTab === 'journal' && (
                      <div className="space-y-4 pt-1">
                        {detailData.journal ? (
                          <>
                            <div className="p-4 rounded-2xl bg-amber-500/5 border border-amber-500/20 space-y-2">
                              <h5 className="text-xs font-bold text-amber-300 flex items-center gap-1.5">
                                <Sparkles className="w-3.5 h-3.5" />
                                <span>상담 회고 요약</span>
                              </h5>
                              <p className="text-xs text-stone-200 leading-relaxed whitespace-pre-wrap">
                                {detailData.journal.summary}
                              </p>
                            </div>

                            <div className="p-4 rounded-2xl bg-stone-950/60 border border-stone-800 space-y-2">
                              <h5 className="text-xs font-bold text-stone-200">💡 핵심 통찰 (Key Insights)</h5>
                              <p className="text-xs text-stone-300 leading-relaxed whitespace-pre-wrap">
                                {detailData.journal.key_insights}
                              </p>
                            </div>

                            {detailData.journal.action_items && (
                              <div className="p-4 rounded-2xl bg-stone-950/60 border border-stone-800 space-y-2">
                                <h5 className="text-xs font-bold text-emerald-400">🌱 마음 챙김 및 실천 제안</h5>
                                <p className="text-xs text-stone-300 leading-relaxed whitespace-pre-wrap">
                                  {detailData.journal.action_items}
                                </p>
                              </div>
                            )}
                          </>
                        ) : (
                          <div className="py-8 text-center text-xs text-stone-500">
                            상담이 완주되지 않고 종료되어 성찰 저널이 작성되지 않았습니다.
                          </div>
                        )}
                      </div>
                    )}

                    {/* 대화 탭 내용 */}
                    {detailTab === 'turns' && (
                      <div className="space-y-3 pt-1">
                        {detailData.turns.map((t) => (
                          <div key={t.turn_number} className="space-y-2">
                            {/* 내담자 발화 */}
                            <div className="flex justify-end">
                              <div className="max-w-[85%] rounded-2xl rounded-tr-sm bg-amber-600/20 border border-amber-500/30 p-3 text-xs text-amber-100">
                                <span className="block text-[10px] text-amber-400/70 font-semibold mb-1">
                                  내 질문 / 응답 #{t.turn_number}
                                </span>
                                <p className="leading-relaxed whitespace-pre-wrap">{t.user_message}</p>
                              </div>
                            </div>
                            {/* AI 상담사 답변 */}
                            <div className="flex justify-start">
                              <div className="max-w-[85%] rounded-2xl rounded-tl-sm bg-stone-950 border border-stone-800 p-3 text-xs text-stone-300">
                                <span className="block text-[10px] text-stone-500 font-semibold mb-1">
                                  주역 상담사 AI #{t.turn_number}
                                </span>
                                <p className="leading-relaxed whitespace-pre-wrap">{t.agent_response}</p>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* 상담 계속 이어가기 액션 영역 */}
                    <div className="mt-4 p-4 rounded-2xl bg-stone-950/80 border border-stone-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-inner">
                      <div>
                        <h5 className="text-xs font-bold text-stone-200 flex items-center gap-1.5">
                          <MessageCircle className="w-3.5 h-3.5 text-amber-400" />
                          <span>이 상담 계속 이어가기</span>
                        </h5>
                        <p className="text-[11px] text-stone-400 mt-1">
                          {detailData.status === 'safety_redirect'
                            ? '안전 지원으로 종결된 세션은 이어갈 수 없습니다.'
                            : detailData.turns.length >= 15
                            ? '최대 대화 턴(15턴)에 도달하여 완료된 상담입니다.'
                            : '이 상담을 메인 대화창으로 불러와 성찰과 대화를 계속 나눕니다.'}
                        </p>
                      </div>

                      {detailData.status !== 'safety_redirect' && detailData.turns.length < 15 && (
                        <div>
                          {(profile?.credit ?? 0) < 10 ? (
                            <div className="flex flex-col items-end gap-1">
                              <button
                                disabled
                                className="px-3.5 py-1.5 text-xs rounded-xl bg-stone-800 text-stone-500 border border-stone-700/50 cursor-not-allowed font-medium"
                              >
                                이어서 대화하기 (10C)
                              </button>
                              <span className="text-[10px] text-amber-500/90">
                                크레딧 부족 (12시간 뒤 자동 충전)
                              </span>
                            </div>
                          ) : (
                            <button
                              onClick={() => {
                                if (onResumeSession && detailData) {
                                  onResumeSession(detailData);
                                  onClose();
                                }
                              }}
                              className="px-3.5 py-1.5 text-xs rounded-xl bg-amber-600/90 hover:bg-amber-500 text-stone-950 font-semibold transition cursor-pointer shadow-md shadow-amber-950/20 flex items-center gap-1"
                            >
                              <MessageCircle className="w-3.5 h-3.5" />
                              <span>이어서 대화하기 (10C)</span>
                            </button>
                          )}
                        </div>
                      )}
                    </div>

                    {/* 하단 삭제 액션 */}
                    <div className="pt-4 border-t border-stone-800 flex justify-between items-center text-xs text-stone-500">
                      <span>개인정보 권리보장에 따라 언제든 기록을 영구 파기할 수 있습니다.</span>
                      <button
                        onClick={() => handleDeleteRecord(selectedSessionId)}
                        disabled={isDeleting}
                        className="flex items-center gap-1 text-red-400 hover:text-red-300 hover:bg-red-950/40 px-2.5 py-1.5 rounded-lg border border-red-900/60 transition cursor-pointer disabled:opacity-50"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                        <span>{isDeleting ? '삭제 중...' : '기록 파기'}</span>
                      </button>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
};
