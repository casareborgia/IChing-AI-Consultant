'use client';

import React, { useState, useRef, useEffect } from 'react';
import Link from 'next/link';
import { motion, AnimatePresence } from 'framer-motion';
import { Compass, Sparkles, Feather, ArrowRight, RotateCcw, LogIn, LogOut, User, BookOpen } from 'lucide-react';

import { CastResult, ChatMessage as ChatMessageType, ConsultationStep, AnyReportData, PreCounselingReportV2, JournalSummary } from '../types/iching';
import { AVAILABLE_FIXTURES, getFixtureCastResult } from '../components/hexagram/fixtures';
import { HexagramStickyHeader } from '../components/hexagram/HexagramStickyHeader';
import { HexagramReportView } from '../components/hexagram/HexagramReportView';
import { ChatMessage } from '../components/chat/ChatMessage';
import { ChatInput } from '../components/chat/ChatInput';
import { TypingIndicator } from '../components/chat/TypingIndicator';
import { CrisisSupportCard } from '../components/safety/CrisisSupportCard';
import { JournalSummaryCard } from '../components/journal/JournalSummaryCard';
import { startConsultationApi, sendConsultationTurnApi, previewConsultationApi, claimAndStartConsultationApi, ConsultationRecordDetail } from '../lib/api';
import { AuthModal } from '../components/auth/AuthModal';
import { AccountModal } from '../components/auth/AccountModal';
import { ConsultationHistoryModal } from '../components/journal/ConsultationHistoryModal';
import { ReconsentModal } from '../components/legal/ReconsentModal';
import { useAuth } from '../context/AuthContext';
import { usePublicConfig } from '../lib/publicConfig';
import {
  createIdempotencyKey,
  fetchOperationStatus,
  CreditOperationError,
} from '../lib/creditOperation';
import { MicroLandingSection } from '../components/landing/MicroLandingSection';
import { Footer } from '../components/layout/Footer';

const EXAMPLE_QUESTIONS = [
  '새로운 이직 기회가 왔는데, 지금 옮기는 것이 맞을까요?',
  '어려운 결정을 앞두고 마음이 자꾸 흔들리고 조급해집니다.',
  '관계에서 거리를 두어야 할지, 먼저 손을 내밀어야 할지 고민입니다.',
  '새로운 프로젝트를 시작하려는데 준비가 충분한지 불안합니다.',
];

export default function Home() {
  const { user, session, profile, signOut, updateCredit, isConsentRecorded, checkConsent } = useAuth();
  const { config } = usePublicConfig();
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [step, setStep] = useState<ConsultationStep>('intake');
  const [question, setQuestion] = useState('');
  const [sessionId, setSessionId] = useState<string>('');
  const [castResult, setCastResult] = useState<CastResult | null>(null);
  const [messages, setMessages] = useState<ChatMessageType[]>([]);
  const [firstAiMessage, setFirstAiMessage] = useState<ChatMessageType | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [journal, setJournal] = useState<JournalSummary | null>(null);

  // 멱등키 생명주기 관리: 사용자 전송 시 생성, 실패 후 재시도 시 동일 키 보존, 새로 작성 시 새 키 생성
  const intakeKeyRef = useRef<string>(createIdempotencyKey());
  const turnKeyRef = useRef<string>(createIdempotencyKey());

  // 에러 및 202 복구 상태
  const [intakeError, setIntakeError] = useState<{
    message: string;
    operationId?: string;
    canRetrySameKey: boolean;
  } | null>(null);
  const [turnError, setTurnError] = useState<{
    message: string;
    userMessage: string;
    operationId?: string;
    canRetrySameKey: boolean;
  } | null>(null);
  const [recoveryLoading, setRecoveryLoading] = useState(false);

  const [isPreviewSession, setIsPreviewSession] = useState<boolean>(false);
  const [isAccountModalOpen, setIsAccountModalOpen] = useState<boolean>(false);
  const [isHistoryModalOpen, setIsHistoryModalOpen] = useState<boolean>(false);
  const [isReconsentModalOpen, setIsReconsentModalOpen] = useState<boolean>(false);
  const [pendingConsentAction, setPendingConsentAction] = useState<'start_consultation' | 'claim_consultation' | null>(null);
  const [isResumeChatOpen, setIsResumeChatOpen] = useState<boolean>(false);

  const chatEndRef = useRef<HTMLDivElement>(null);

  // 새 메시지 시 스크롤
  useEffect(() => {
    if (step === 'counseling' || (step === 'completed' && isResumeChatOpen)) {
      chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isLoading, step, isResumeChatOpen]);

  const [reportData, setReportData] = useState<AnyReportData | undefined>(undefined);
  const [reportStatus, setReportStatus] = useState<'ready' | 'failed' | 'not_requested'>('ready');
  const [reportErrorCode, setReportErrorCode] = useState<string | undefined>(undefined);
  const [activeFixtureKey, setActiveFixtureKey] = useState<string | null>(null);

  // 통합 검증 및 E2E 테스트용 ?fixture= 파라미터 감지 및 주입
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const params = new URLSearchParams(window.location.search);
    const fixtureKey = params.get('fixture');
    if (fixtureKey && AVAILABLE_FIXTURES[fixtureKey]) {
      setActiveFixtureKey(fixtureKey);
      const f = AVAILABLE_FIXTURES[fixtureKey];
      setStep('report');
      setQuestion('이직을 고민하고 있습니다. 지금 옮기는 것이 좋은 선택일까요?');
      setReportData(f.reportData || undefined);
      setReportStatus(f.reportStatus || 'ready');
      setReportErrorCode(f.reportErrorCode);
      if (f.reportData && (f.reportData as PreCounselingReportV2).schema_version === '2.0') {
        setCastResult(getFixtureCastResult(f.reportData as PreCounselingReportV2));
      } else {
        setCastResult({
          originalHexId: 21,
          transformedHexId: 21,
          lines: [
            { position: 1, value: 7, isYang: true, isChanging: false },
            { position: 2, value: 8, isYang: false, isChanging: false },
            { position: 3, value: 8, isYang: false, isChanging: false },
            { position: 4, value: 7, isYang: true, isChanging: false },
            { position: 5, value: 8, isYang: false, isChanging: false },
            { position: 6, value: 7, isYang: true, isChanging: false },
          ],
          changingPositions: [],
        });
      }
    }
  }, []);

  // 1. 상담 시작 및 괘 도출 (비회원은 무료 리포트, 회원은 정식 상담 시작)
  const handleStartConsultation = async (submittedQuestion?: string, useSameKey: boolean = false) => {
    const q = submittedQuestion || question;
    if (!q.trim() || isLoading || isSubmitting) return;

    // A. 비회원인 경우: 로그인 요구 없이 무료 괘 도출 및 리포트(0C) 호출!
    if (!user) {
      setIsSubmitting(true);
      setIsLoading(true);
      setIntakeError(null);
      setStep('casting'); // 괘 도출 애니메이션 단계

      try {
        const [apiRes] = await Promise.all([
          previewConsultationApi(q),
          new Promise((resolve) => setTimeout(resolve, 1400)),
        ]);

        if (apiRes.is_crisis) {
          setSessionId(apiRes.session_id);
          setStep('safety_redirect');
          return;
        }

        setSessionId(apiRes.session_id);
        setCastResult(apiRes.castResult);
        setReportData(apiRes.report_data || undefined);
        setIsPreviewSession(true);

        const initialUserMsg: ChatMessageType = {
          id: `user-init-${Date.now()}`,
          sender: 'user',
          content: q,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        };

        const firstMsg: ChatMessageType = {
          id: 'msg-1',
          sender: 'assistant',
          content: apiRes.user_facing_message || '주역 심층 상담이 준비되었습니다.',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        };

        setFirstAiMessage(firstMsg);
        setMessages([initialUserMsg, firstMsg]);
        setStep('report');
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : '주역 리포트를 생성하지 못했습니다. 잠시 후 다시 시도해 주세요.';
        setIntakeError({ message: msg, canRetrySameKey: true });
        setStep('intake');
      } finally {
        setIsLoading(false);
        setIsSubmitting(false);
      }
      return;
    }

    // B. 로그인된 회원인 경우: 법적 동의 상태 확인 (자동 기록 제거 -> 재동의 모달 팝업)
    if (user && !isConsentRecorded) {
      setPendingConsentAction('start_consultation');
      setIsReconsentModalOpen(true);
      return;
    }

    if (!useSameKey) {
      intakeKeyRef.current = createIdempotencyKey();
    }
    const currentKey = intakeKeyRef.current;

    setIsSubmitting(true);
    setIsLoading(true);
    setIntakeError(null);
    setStep('casting'); // 괘 도출 애니메이션 단계
    setIsPreviewSession(false);

    try {
      // 1.2초간 명상적 드로잉 연출과 병렬로 API 호출
      const [apiRes] = await Promise.all([
        startConsultationApi(q, user?.id || '00000000-0000-0000-0000-000000000000', {
          idempotencyKey: currentKey,
        }),
        new Promise((resolve) => setTimeout(resolve, 1400)),
      ]);

      if (typeof apiRes.remainingCredits === 'number') {
        updateCredit(apiRes.remainingCredits);
      }

      if (apiRes.isCrisis) {
        setSessionId(apiRes.sessionId);
        setStep('safety_redirect');
        return;
      }

      if (apiRes.castResult && apiRes.firstMessage) {
        setSessionId(apiRes.sessionId);
        setCastResult(apiRes.castResult);
        setFirstAiMessage(apiRes.firstMessage);
        setReportData(apiRes.reportData);
        setReportStatus(apiRes.reportStatus || 'ready');
        setReportErrorCode(apiRes.reportErrorCode);

        const initialUserMsg: ChatMessageType = {
          id: `user-init-${Date.now()}`,
          sender: 'user',
          content: q,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        };

        setMessages([initialUserMsg, apiRes.firstMessage]);
        setStep('report');
      }
    } catch (err: unknown) {
      let msg = '상담을 시작하는 중 오류가 발생했습니다.';
      let opId: string | undefined;
      let canRetrySameKey = true;

      if (err instanceof CreditOperationError) {
        msg = err.message;
        opId = err.operationId;
        canRetrySameKey = err.canRetrySameKey;
        if (typeof err.remainingCredits === 'number') {
          updateCredit(err.remainingCredits);
        }
        if (err.code === 'CONSENT_REQUIRED' || err.status === 403) {
          setIsAuthModalOpen(true);
        }
      } else if (err instanceof Error) {
        msg = err.message;
      }

      const cleanMsg = typeof msg === 'string' && msg !== '[object Object]' ? msg : '상담 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.';
      setIntakeError({ message: cleanMsg, operationId: opId, canRetrySameKey });
      setStep('intake');
    } finally {
      setIsLoading(false);
      setIsSubmitting(false);
    }
  };

  // 지연된 작업의 처리 상태를 수동으로 재조회하는 복구 핸들러
  const handleCheckOperationStatus = async (operationId: string) => {
    if (!session || recoveryLoading) return;
    setRecoveryLoading(true);
    try {
      const op = await fetchOperationStatus(operationId, session.access_token);
      if (typeof op.remaining_credits === 'number') {
        updateCredit(op.remaining_credits);
      }
      if (op.operation_status === 'PROCESSING') {
        alert('아직 AI 상담 응답을 생성하는 중입니다. 잠시 후 다시 확인해 주세요.');
      } else if (op.operation_status === 'SUCCEEDED' || op.operation_status === 'RELEASED') {
        alert('작업 처리가 완료되었습니다. 같은 요청으로 재시도하시면 결과를 즉시 불러옵니다.');
      } else {
        alert(`작업 상태: ${op.operation_status}`);
      }
    } catch (e) {
      const errMsg = e instanceof Error ? e.message : '작업 상태 조회 실패';
      alert(errMsg);
    } finally {
      setRecoveryLoading(false);
    }
  };

  // 3. 괘 해석 리포트 확인 후 본격적인 상담 대화 진입
  const handleProceedToCounsel = async () => {
    if (!user) {
      setIsAuthModalOpen(true);
      return;
    }

    // 비회원 미리보기 세션에서 정식 상담으로 전환(세션 클레임 + 10C 차감)
    if (isPreviewSession && sessionId) {
      if (!isConsentRecorded) {
        setPendingConsentAction('claim_consultation');
        setIsReconsentModalOpen(true);
        return;
      }

      setIsSubmitting(true);
      setIsLoading(true);
      try {
        const claimRes = await claimAndStartConsultationApi(sessionId, user.id, {
          idempotencyKey: createIdempotencyKey(),
        });

        if (typeof claimRes.remainingCredits === 'number') {
          updateCredit(claimRes.remainingCredits);
        }

        setIsPreviewSession(false);
        if (claimRes.firstMessage) {
          setFirstAiMessage(claimRes.firstMessage);
          setMessages((prev) => {
            const initialUserMsg = prev[0] || {
              id: `user-init-${Date.now()}`,
              sender: 'user',
              content: question,
              timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            };
            return [initialUserMsg, claimRes.firstMessage];
          });
        }
        setStep('counseling');
      } catch (err: unknown) {
        let msg = '상담 세션을 등록하는 중 오류가 발생했습니다.';
        if (err instanceof CreditOperationError) {
          msg = err.message;
          if (typeof err.remainingCredits === 'number') {
            updateCredit(err.remainingCredits);
          }
          if (err.code === 'CONSENT_REQUIRED' || err.status === 403) {
            setIsAuthModalOpen(true);
          }
        } else if (err instanceof Error) {
          msg = err.message;
        }
        alert(msg);
      } finally {
        setIsLoading(false);
        setIsSubmitting(false);
      }
      return;
    }

    setStep('counseling');
  };


  // 4. 상담 턴 전송 (멱등키 전송 및 이중 전송 방지)
  const handleSendMessage = async (
    text: string,
    useSameKey: boolean = false,
    appendUserMessage: boolean = !useSameKey
  ) => {
    if (!text.trim() || isLoading || isSubmitting || !castResult) return;

    if (!useSameKey) {
      turnKeyRef.current = createIdempotencyKey();
    }
    setTurnError(null);
    const currentKey = turnKeyRef.current;

    const userMsg: ChatMessageType = {
      id: `user-${Date.now()}`,
      sender: 'user',
      content: text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    if (appendUserMessage) {
      setMessages((prev) => [...prev, userMsg]);
    }
    setIsSubmitting(true);
    setIsLoading(true);

    try {
      const turnCount = Math.floor(messages.length / 2) + 1;
      const apiRes = await sendConsultationTurnApi(sessionId, text, turnCount, castResult, undefined, {
        idempotencyKey: currentKey,
      });

      if (typeof apiRes.remainingCredits === 'number') {
        updateCredit(apiRes.remainingCredits);
      }

      setMessages((prev) => [...prev, apiRes.replyMessage]);

      if (apiRes.isFinal) {
        if (apiRes.journal) {
          setJournal(apiRes.journal);
        }
        setStep('completed');
      }
      setTurnError(null);
    } catch (err: unknown) {
      console.error(err);
      let errorText = '답변을 불러오는 중 문제가 발생했습니다. 다시 시도해 주세요.';
      if (err instanceof CreditOperationError) {
        errorText = err.message;
        if (typeof err.remainingCredits === 'number') {
          updateCredit(err.remainingCredits);
        }
        if (err.code === 'CONSENT_REQUIRED' || err.status === 403) {
          setIsAuthModalOpen(true);
        }
      } else if (err instanceof Error) {
        errorText = err.message;
      }

      setTurnError({
        message: errorText,
        userMessage: text,
        operationId: err instanceof CreditOperationError ? err.operationId : undefined,
        canRetrySameKey: err instanceof CreditOperationError ? err.canRetrySameKey : true,
      });

      setMessages((prev) => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          sender: 'system',
          content: errorText,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ]);
    } finally {
      setIsLoading(false);
      setIsSubmitting(false);
    }
  };

  // 상담 리셋 (새로운 멱등키 초기화)
  const handleRestart = () => {
    setStep('intake');
    setQuestion('');
    setCastResult(null);
    setMessages([]);
    setFirstAiMessage(null);
    setJournal(null);
    setSessionId('');
    setReportData(undefined);
    setIntakeError(null);
    setTurnError(null);
    setIsResumeChatOpen(false);
    intakeKeyRef.current = createIdempotencyKey();
    turnKeyRef.current = createIdempotencyKey();
  };

  // 과거 상담 기록 보관함에서 세션을 불러와 상담 이어가기
  const handleResumeFromHistory = (record: ConsultationRecordDetail) => {
    if (!record || !record.session_id) return;

    setSessionId(record.session_id);
    setQuestion(record.raw_question || record.clarified_question || '');

    // 대화 턴들을 ChatMessage 형태로 재구성
    const reconstructedMessages: ChatMessageType[] = [];
    (record.turns || []).forEach((t) => {
      if (t.user_message) {
        reconstructedMessages.push({
          id: `${t.turn_number}-user`,
          sender: 'user',
          content: t.user_message,
          timestamp: t.created_at || '',
        });
      }
      if (t.agent_response) {
        reconstructedMessages.push({
          id: `${t.turn_number}-assistant`,
          sender: 'assistant',
          content: t.agent_response,
          timestamp: t.created_at || '',
        });
      }
    });
    setMessages(reconstructedMessages);

    // 괘 리포트 데이터가 있으면 복원
    if (record.report_data) {
      setReportData(record.report_data);
      setReportStatus('ready');
    }

    // 저널이 있거나 5턴 이상 완료된 세션인 경우
    if (record.journal || record.turns.length >= 5) {
      if (record.journal) {
        setJournal({
          clarifiedQuestion: record.clarified_question || record.raw_question,
          hexagramSummary: record.journal.summary,
          keyInsights: record.journal.key_insights ? [record.journal.key_insights] : [],
          suggestedAction: record.journal.action_items || '',
          createdAt: record.journal.created_at || record.created_at || '',
          cardData: undefined,
          isCrisis: record.status === 'safety_redirect',
        });
      }
      setStep('completed');
      setIsResumeChatOpen(true);
    } else {
      // 5턴 미만 진행 중 세션인 경우 바로 대화 단계로 복원
      setStep('counseling');
    }

    // 멱등키 재발급
    turnKeyRef.current = createIdempotencyKey();
  };

  return (
    <div className="min-h-screen bg-stone-950 text-stone-100 flex flex-col selection:bg-amber-500/30 selection:text-amber-200">
      {/* 헤더 */}
      <header className="border-b border-stone-800/60 bg-stone-950/70 backdrop-blur-md px-4 py-3.5 sticky top-0 z-20">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2.5 cursor-pointer" onClick={handleRestart}>
            <div className="w-8 h-8 rounded-lg bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400">
              <Compass className="w-4 h-4" />
            </div>
            <div>
              <h1 className="text-base font-serif font-semibold tracking-wide text-stone-100 flex items-center gap-1.5">
                마음지기 <span className="text-xs font-sans text-amber-500/80 font-normal">주역 심층 AI 상담 · I-Ching Oracle</span>
              </h1>
              <p className="text-[10px] text-stone-500 font-light">
                변화의 지혜를 거울삼는 성찰 대화
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* 웰컴 크레딧 배지 (클릭 시 로그인 모달) */}
            <button
              onClick={() => !user && setIsAuthModalOpen(true)}
              className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-amber-500/10 border border-amber-500/20 text-[11px] text-amber-300 font-medium hover:bg-amber-500/20 transition cursor-pointer"
            >
              <Sparkles className="w-3.5 h-3.5 text-amber-400" />
              <span>
                {user
                  ? (profile?.credit !== null && profile?.credit !== undefined
                      ? `${profile.credit} 크레딧`
                      : '잔액 확인 필요')
                  : `✨ ${config.welcome_credits} 웰컴 크레딧`}
              </span>
            </button>

            {/* 로그인 / 로그아웃 버튼 */}
            {user ? (
              <div className="flex items-center gap-2">
                {user.email === 'casareborgia@gmail.com' && (
                  <Link
                    href="/admin"
                    className="flex items-center gap-1 text-xs px-2.5 py-1 rounded-lg bg-amber-500/10 text-amber-300 border border-amber-500/30 hover:bg-amber-500/20 font-medium transition"
                    title="운영자 대시보드"
                  >
                    <span>🛠️ 대시보드</span>
                  </Link>
                )}
                <button
                  onClick={() => setIsHistoryModalOpen(true)}
                  className="flex items-center gap-1.5 text-xs text-amber-300/90 hover:text-amber-200 px-2.5 py-1.5 rounded-lg bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/30 transition cursor-pointer"
                  title="내 지난 상담 기록 및 저널 보관함"
                >
                  <BookOpen className="w-3.5 h-3.5 text-amber-400" />
                  <span className="hidden sm:inline font-medium">내 기록</span>
                </button>
                <button
                  onClick={() => setIsAccountModalOpen(true)}
                  className="flex items-center gap-1.5 text-xs text-stone-300 hover:text-stone-100 px-2.5 py-1.5 rounded-lg bg-stone-900 hover:bg-stone-800 border border-stone-800 transition cursor-pointer"
                  title="계정 관리 및 탈퇴"
                >
                  <User className="w-3.5 h-3.5 text-amber-400" />
                  <span className="max-w-[120px] truncate">{user.email?.split('@')[0] || '내 계정'}</span>
                </button>
                <button
                  onClick={() => signOut()}
                  className="text-xs text-stone-400 hover:text-stone-200 flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-stone-900 border border-stone-800 transition cursor-pointer"
                  title="로그아웃"
                >
                  <LogOut className="w-3.5 h-3.5" />
                  <span className="hidden sm:inline">로그아웃</span>
                </button>
              </div>
            ) : (
              <button
                onClick={() => setIsAuthModalOpen(true)}
                className="text-xs font-medium text-stone-900 bg-amber-400 hover:bg-amber-300 flex items-center gap-1.5 px-3 py-1.5 rounded-lg shadow-sm transition cursor-pointer"
              >
                <LogIn className="w-3.5 h-3.5" />
                <span>로그인 / 간편가입</span>
              </button>
            )}

            {step !== 'intake' && (
              <button
                onClick={handleRestart}
                className="text-xs text-stone-400 hover:text-stone-200 flex items-center gap-1 px-3 py-1.5 rounded-lg bg-stone-900 border border-stone-800 transition cursor-pointer"
              >
                <RotateCcw className="w-3 h-3" />
                <span>처음으로</span>
              </button>
            )}
          </div>
        </div>
      </header>

      {/* 상담 중 상단 Sticky Header (본괘/지괘 요약 및 원래 질문) */}
      {step === 'counseling' && castResult && (
        <HexagramStickyHeader castResult={castResult} userQuestion={question} />
      )}

      {/* 메인 컨텐츠 영역 */}
      <main className="flex-1 max-w-4xl w-full mx-auto p-4 sm:p-6 flex flex-col">
        <AnimatePresence mode="wait">
          {/* 1. 인테이크 단계 (고민 입력 & 마이크로 랜딩) */}
          {step === 'intake' && (
            <motion.div
              key="intake"
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -15 }}
              className="max-w-3xl w-full mx-auto py-6 sm:py-10"
            >
              <div className="text-center mb-8 max-w-xl mx-auto">
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20 text-xs mb-4">
                  <Feather className="w-3.5 h-3.5" />
                  <span>마음을 가다듬는 시간</span>
                </div>
                <h2 className="text-2xl sm:text-3xl font-serif font-normal text-stone-100 leading-snug">
                  지금 마음에 품고 계신<br />
                  <span className="text-amber-400/90 font-medium">고민과 변화의 질문</span>은 무엇인가요?
                </h2>
                <p className="text-xs sm:text-sm text-stone-400 mt-3 font-light leading-relaxed">
                  주역은 미래를 맞히는 예언이 아니라, 지금 당신이 마주한 상황의 본질과<br className="hidden sm:block" />
                  스스로 답을 찾아갈 수 있는 깊은 거울을 비춰줍니다.
                </p>
              </div>

              <div className="max-w-xl mx-auto bg-stone-900/80 border border-stone-800 rounded-2xl p-4 sm:p-5 shadow-2xl backdrop-blur-md">
                <textarea
                  rows={4}
                  value={question}
                  onChange={(e) => {
                    setQuestion(e.target.value);
                    if (intakeError) setIntakeError(null);
                  }}
                  placeholder="예: 새로운 이직 기회가 찾아왔는데, 지금 떠나는 것이 좋은 선택일지 마음이 복잡합니다..."
                  className="w-full bg-stone-950/60 border border-stone-800/80 rounded-xl p-3.5 text-sm text-stone-100 placeholder-stone-600 focus:outline-none focus:border-amber-500/50 resize-none transition"
                />

                {intakeError && (
                  <div className="mt-3 p-3 rounded-xl bg-red-950/40 border border-red-800/60 text-xs text-red-200 flex flex-col gap-2">
                    <div className="flex items-start gap-2">
                      <span className="font-semibold text-red-400">안내:</span>
                      <span className="flex-1">{intakeError.message}</span>
                    </div>
                    <div className="flex flex-wrap items-center gap-2 mt-1">
                      {intakeError.canRetrySameKey && (
                        <button
                          type="button"
                          onClick={() => handleStartConsultation(undefined, true)}
                          disabled={isLoading || isSubmitting}
                          className="px-2.5 py-1 bg-red-900/60 hover:bg-red-800/60 border border-red-700/60 rounded text-[11px] text-red-100 font-medium transition cursor-pointer disabled:opacity-50"
                        >
                          같은 요청으로 재시도
                        </button>
                      )}
                      {intakeError.operationId && (
                        <button
                          type="button"
                          onClick={() => handleCheckOperationStatus(intakeError.operationId!)}
                          disabled={recoveryLoading}
                          className="px-2.5 py-1 bg-stone-800 hover:bg-stone-700 border border-stone-700 rounded text-[11px] text-amber-300 font-medium transition cursor-pointer disabled:opacity-50"
                        >
                          {recoveryLoading ? '확인 중...' : '처리 상태 다시 확인'}
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => handleStartConsultation(undefined, false)}
                        disabled={isLoading || isSubmitting}
                        className="px-2.5 py-1 bg-stone-800/60 hover:bg-stone-700/60 border border-stone-700/60 rounded text-[11px] text-stone-300 transition cursor-pointer disabled:opacity-50"
                      >
                        새로운 질문으로 다시 시도
                      </button>
                    </div>
                  </div>
                )}

                <div className="mt-4 flex flex-col sm:flex-row items-center justify-between gap-3">
                  {!user ? (
                    <span className="text-[11px] text-amber-400/90 flex items-center gap-1">
                      <Sparkles className="w-3.5 h-3.5" />
                      <span>리포트 무료 열람 · 가입 시 {config.welcome_credits} 웰컴 크레딧 자동 지급</span>
                    </span>
                  ) : (
                    <span className="text-[11px] text-stone-400">
                      보유 잔액:{' '}
                      <strong className="text-amber-300">
                        {profile?.credit !== null && profile?.credit !== undefined
                          ? `${profile.credit} 크레딧`
                          : '잔액 확인 필요'}
                      </strong>{' '}
                      (대화 1회: 10C)
                    </span>
                  )}

                  <button
                    onClick={() => handleStartConsultation(undefined, false)}
                    disabled={!question.trim() || isLoading || isSubmitting}
                    className="w-full sm:w-auto px-6 py-3 rounded-xl bg-amber-500 hover:bg-amber-400 disabled:bg-stone-800 text-stone-950 disabled:text-stone-600 font-medium text-sm transition-all flex items-center justify-center gap-2 cursor-pointer disabled:cursor-not-allowed shadow-lg shadow-amber-950/30 active:scale-[0.98]"
                  >
                    <span>{user ? '마음을 모아 괘 도출하기' : '✨ 무료로 괘 도출 및 리포트 보기'}</span>
                    <ArrowRight className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {/* 추천 예시 질문 칩 */}
              <div className="mt-6 max-w-xl mx-auto">
                <span className="text-[11px] text-stone-500 block mb-2 font-medium">
                  이런 질문으로 시작해 볼 수 있습니다:
                </span>
                <div className="flex flex-wrap gap-2">
                  {EXAMPLE_QUESTIONS.map((eq, i) => (
                    <button
                      key={i}
                      onClick={() => {
                        setQuestion(eq);
                      }}
                      className="text-xs text-stone-400 hover:text-stone-200 bg-stone-900/60 hover:bg-stone-900 border border-stone-800/80 px-3 py-1.5 rounded-lg transition text-left cursor-pointer"
                    >
                      {eq}
                    </button>
                  ))}
                </div>
              </div>

              {/* 고품격 마이크로 랜딩 섹션 (How it Works, Core Values, Welcome Badge) */}
              <MicroLandingSection onSelectQuestion={(q) => setQuestion(q)} />
            </motion.div>
          )}

          {/* 2. 괘 도출 애니메이션 단계 (Casting) */}
          {step === 'casting' && (
            <motion.div
              key="casting"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex flex-col items-center justify-center my-auto py-16 text-center"
            >
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ duration: 8, repeat: Infinity, ease: 'linear' }}
                className="w-20 h-20 rounded-full border-2 border-dashed border-amber-500/40 flex items-center justify-center mb-6"
              >
                <Compass className="w-8 h-8 text-amber-500 animate-pulse" />
              </motion.div>

              <h3 className="text-xl font-serif text-stone-100 mb-2">
                음양(陰陽)의 기운을 모아 괘를 도출하고 있습니다
              </h3>
              <p className="text-xs text-stone-400 font-light max-w-sm">
                주자의 점법에 따라 6개의 효(爻)를 차례로 세우고 당신의 상황에 닿은 고전 주석을 살핍니다.
              </p>
            </motion.div>
          )}

          {/* 3. 괘 도출 결과 및 괘 해석 리포트 단계 (Revealed & Report) */}
          {(step === 'revealed' || step === 'report') && castResult && (
            <motion.div
              key="report"
              initial={{ opacity: 0, scale: 0.98 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, y: -20 }}
              className="my-auto py-4"
            >
              {activeFixtureKey && (
                <div className="mb-4 p-3 bg-stone-900 border border-amber-500/30 rounded-2xl flex items-center justify-between gap-3 text-xs text-stone-300">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-amber-400">🧪 검증 Fixture:</span>
                    <select
                      value={activeFixtureKey}
                      onChange={(e) => {
                        const nextKey = e.target.value;
                        const url = new URL(window.location.href);
                        url.searchParams.set('fixture', nextKey);
                        window.location.href = url.toString();
                      }}
                      className="bg-stone-950 border border-stone-700 text-stone-200 rounded-lg px-2 py-1 text-xs"
                    >
                      {Object.entries(AVAILABLE_FIXTURES).map(([k, v]) => (
                        <option key={k} value={k}>
                          {v.name}
                        </option>
                      ))}
                    </select>
                  </div>
                  <button
                    onClick={() => {
                      const url = new URL(window.location.href);
                      url.searchParams.delete('fixture');
                      window.location.href = url.pathname;
                    }}
                    className="text-stone-400 hover:text-stone-100 underline"
                  >
                    일반 화면으로 복귀
                  </button>
                </div>
              )}
              <HexagramReportView
                castResult={castResult}
                userQuestion={question}
                firstMessage={firstAiMessage || messages[1]}
                reportData={reportData}
                reportStatus={reportStatus}
                reportErrorCode={reportErrorCode}
                onProceedToCounsel={handleProceedToCounsel}
                isLoggedIn={Boolean(user)}
              />
            </motion.div>
          )}

          {/* 4. 심층 상담 대화 단계 (Counseling) */}
          {step === 'counseling' && (
            <motion.div
              key="counseling"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex flex-col h-[calc(100vh-140px)] sm:h-[700px] w-full"
            >
              {/* 대화 스크롤 영역 */}
              <div className="flex-1 overflow-y-auto px-1 sm:px-2 py-4">
                {messages.map((msg) => (
                  <ChatMessage key={msg.id} message={msg} />
                ))}

                {isLoading && <TypingIndicator />}
                <div ref={chatEndRef} />
              </div>

              {/* 하단 입력 영역 */}
              <div className="pt-3 border-t border-stone-800/80">
                {turnError && (
                  <div className="mb-3 p-3 rounded-xl bg-red-950/40 border border-red-800/60 text-xs text-red-200">
                    <p>{turnError.message}</p>
                    <div className="flex flex-wrap gap-2 mt-2">
                      {turnError.canRetrySameKey && (
                        <button
                          type="button"
                          onClick={() => handleSendMessage(turnError.userMessage, true, false)}
                          disabled={isLoading || isSubmitting}
                          className="px-2.5 py-1 rounded bg-red-900/60 border border-red-700/60 disabled:opacity-50"
                        >
                          같은 요청으로 재시도
                        </button>
                      )}
                      {turnError.operationId && (
                        <button
                          type="button"
                          onClick={() => handleCheckOperationStatus(turnError.operationId!)}
                          disabled={recoveryLoading}
                          className="px-2.5 py-1 rounded bg-stone-800 border border-stone-700 text-amber-300 disabled:opacity-50"
                        >
                          {recoveryLoading ? '확인 중...' : '처리 상태 다시 확인'}
                        </button>
                      )}
                      {!turnError.canRetrySameKey && (
                        <button
                          type="button"
                          onClick={() => handleSendMessage(turnError.userMessage, false, false)}
                          disabled={isLoading || isSubmitting}
                          className="px-2.5 py-1 rounded bg-stone-800 border border-stone-700 disabled:opacity-50"
                        >
                          새 작업으로 다시 시도
                        </button>
                      )}
                    </div>
                  </div>
                )}
                <div className="flex items-center justify-between mb-2 px-1 text-[11px] text-stone-500">
                  <span>되묻는 질문에 떠오르는 생각을 편안히 나눠보세요.</span>
                  <button
                    onClick={() => handleSendMessage('생각이 어느 정도 정리되었습니다. 고맙습니다.')}
                    className="text-amber-500/80 hover:text-amber-400 transition cursor-pointer underline"
                  >
                    상담 마무리하기
                  </button>
                </div>
                <ChatInput
                  onSendMessage={handleSendMessage}
                  isLoading={isLoading}
                  placeholder="상담사에게 전하고 싶은 이야기를 적어주세요..."
                />
              </div>
            </motion.div>
          )}

          {/* 5. 위기 지원 분기 단계 (Safety Redirect) */}
          {step === 'safety_redirect' && (
            <motion.div
              key="safety"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="my-auto py-8"
            >
              <CrisisSupportCard onRestart={handleRestart} />
            </motion.div>
          )}

          {/* 6. 상담 완료 및 저널 요약 단계 (Completed) */}
          {step === 'completed' && journal && (
            <motion.div
              key="completed"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="my-auto py-8"
            >
              <JournalSummaryCard journal={journal} onRestart={handleRestart} sessionId={sessionId || undefined} />

              {/* B안: 종료된 상담 이어가기 진입점 */}
              {!journal.isCrisis && (
                <div className="mt-6 rounded-2xl border border-stone-800/80 bg-stone-900/60 p-5 shadow-lg">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div>
                      <h4 className="text-sm font-semibold text-stone-200">
                        상담 더 이어가기
                      </h4>
                      <p className="text-xs text-stone-400 mt-1">
                        앞서 정한 다짐을 마음에 품고, 마음지기 상담사와 생각을 더 나눌 수 있습니다.
                      </p>
                    </div>

                    {!isResumeChatOpen ? (
                      <div>
                        {(() => {
                          const currentTurns = messages.filter((m) => m.sender === 'user').length;
                          const isTurnLimitReached = currentTurns >= 15;
                          const hasEnoughCredit = (profile?.credit ?? 0) >= 10;

                          if (isTurnLimitReached) {
                            return (
                              <div className="text-right">
                                <span className="inline-block px-3 py-1.5 text-xs text-stone-500 bg-stone-800/80 rounded-lg border border-stone-700/50">
                                  최대 대화 턴(15턴)에 도달했습니다
                                </span>
                              </div>
                            );
                          }

                          if (!hasEnoughCredit) {
                            return (
                              <div className="flex flex-col items-end gap-1">
                                <button
                                  disabled
                                  className="px-4 py-2 text-xs rounded-xl bg-stone-800 text-stone-500 border border-stone-700/50 cursor-not-allowed font-medium"
                                >
                                  이어서 이야기하기 (10C)
                                </button>
                                <span className="text-[11px] text-amber-500/90">
                                  크레딧이 부족합니다 (12시간 뒤 자동 충전)
                                </span>
                              </div>
                            );
                          }

                          return (
                            <button
                              onClick={() => setIsResumeChatOpen(true)}
                              className="px-4 py-2 text-xs rounded-xl bg-amber-600/90 hover:bg-amber-500 text-stone-950 font-semibold transition cursor-pointer shadow-md shadow-amber-950/20"
                            >
                              이어서 이야기하기 (10C)
                            </button>
                          );
                        })()}
                      </div>
                    ) : (
                      <button
                        onClick={() => setIsResumeChatOpen(false)}
                        className="px-3 py-1 text-xs text-stone-400 hover:text-stone-300 bg-stone-800/60 rounded-lg transition self-start sm:self-auto cursor-pointer"
                      >
                        대화창 접기
                      </button>
                    )}
                  </div>

                  {/* 이어서 이야기하기 대화창 열렸을 때 */}
                  {isResumeChatOpen && (
                    <div className="mt-5 pt-5 border-t border-stone-800/80">
                      <div className="space-y-4 mb-5 max-h-[420px] overflow-y-auto px-1">
                        {messages.map((msg) => (
                          <ChatMessage key={msg.id} message={msg} />
                        ))}
                        {isLoading && <TypingIndicator />}
                        <div ref={chatEndRef} />
                      </div>

                      {turnError && (
                        <div className="mb-3 p-3 rounded-xl bg-red-950/40 border border-red-900/60 text-xs text-red-300">
                          {turnError.message}
                        </div>
                      )}

                      {(() => {
                        const currentTurns = messages.filter((m) => m.sender === 'user').length;
                        if (currentTurns >= 15) {
                          return (
                            <p className="text-center text-xs text-stone-500 py-2">
                              세션의 최대 대화 턴(15턴)에 도달하여 상담이 종료되었습니다.
                            </p>
                          );
                        }
                        return (
                          <ChatInput
                            onSendMessage={handleSendMessage}
                            isLoading={isLoading}
                            placeholder="다짐 이후 마음에 남은 생각이나 질문을 편안히 적어주세요..."
                          />
                        );
                      })()}
                    </div>
                  )}
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </main>

      {/* 공통 정책 및 사업자 정보 푸터 */}
      <Footer />

      {/* 소셜 로그인 모달 */}
      <AuthModal isOpen={isAuthModalOpen} onClose={() => setIsAuthModalOpen(false)} />

      {/* 계정 관리 및 회원 탈퇴 모달 */}
      <AccountModal
        isOpen={isAccountModalOpen}
        onClose={() => setIsAccountModalOpen(false)}
        onOpenHistory={() => setIsHistoryModalOpen(true)}
      />

      {/* 내 지난 상담 기록 및 저널 보관함 모달 */}
      <ConsultationHistoryModal
        isOpen={isHistoryModalOpen}
        onClose={() => setIsHistoryModalOpen(false)}
        onResumeSession={handleResumeFromHistory}
      />

      {/* 약관 및 개인정보처리방침 재동의 모달 (미동의 또는 개정 시) */}
      <ReconsentModal
        isOpen={isReconsentModalOpen}
        onClose={() => {
          setIsReconsentModalOpen(false);
          setPendingConsentAction(null);
        }}
        onSuccess={() => {
          setIsReconsentModalOpen(false);
          const action = pendingConsentAction;
          setPendingConsentAction(null);
          if (action === 'start_consultation') {
            handleStartConsultation(undefined, true);
          } else if (action === 'claim_consultation') {
            handleProceedToCounsel();
          }
        }}
      />
    </div>
  );
}
