'use client';

import React, { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Compass, Sparkles, Feather, HelpCircle, ArrowRight, RotateCcw, Check } from 'lucide-react';

import { CastResult, ChatMessage as ChatMessageType, ConsultationStep, JournalSummary } from '../types/iching';
import { HexagramCard } from '../components/hexagram/HexagramCard';
import { HexagramSymbol } from '../components/hexagram/HexagramSymbol';
import { HexagramStickyHeader } from '../components/hexagram/HexagramStickyHeader';
import { ChatMessage } from '../components/chat/ChatMessage';
import { ChatInput } from '../components/chat/ChatInput';
import { TypingIndicator } from '../components/chat/TypingIndicator';
import { CrisisSupportCard } from '../components/safety/CrisisSupportCard';
import { JournalSummaryCard } from '../components/journal/JournalSummaryCard';
import { startConsultationApi, sendConsultationTurnApi } from '../lib/api';

import { MicroLandingSection } from '../components/landing/MicroLandingSection';

const EXAMPLE_QUESTIONS = [
  '새로운 이직 기회가 왔는데, 지금 옮기는 것이 맞을까요?',
  '어려운 결정을 앞두고 마음이 자꾸 흔들리고 조급해집니다.',
  '관계에서 거리를 두어야 할지, 먼저 손을 내밀어야 할지 고민입니다.',
  '새로운 프로젝트를 시작하려는데 준비가 충분한지 불안합니다.',
];

export default function Home() {
  const [step, setStep] = useState<ConsultationStep>('intake');
  const [question, setQuestion] = useState('');
  const [sessionId, setSessionId] = useState<string>('');
  const [castResult, setCastResult] = useState<CastResult | null>(null);
  const [messages, setMessages] = useState<ChatMessageType[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [journal, setJournal] = useState<JournalSummary | null>(null);

  const chatEndRef = useRef<HTMLDivElement>(null);

  // 새 메시지 시 스크롤
  useEffect(() => {
    if (step === 'counseling') {
      chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isLoading, step]);

  // 1. 상담 시작 및 괘 도출
  const handleStartConsultation = async (submittedQuestion?: string) => {
    const q = submittedQuestion || question;
    if (!q.trim() || isLoading) return;

    setIsLoading(true);
    setStep('casting'); // 괘 도출 애니메이션 단계

    try {
      // 1.2초간 명상적 드로잉 연출
      const [apiRes] = await Promise.all([
        startConsultationApi(q),
        new Promise((resolve) => setTimeout(resolve, 1400)),
      ]);

      if (apiRes.isCrisis) {
        setStep('safety_redirect');
        return;
      }

      if (apiRes.castResult && apiRes.firstMessage) {
        setSessionId(apiRes.sessionId);
        setCastResult(apiRes.castResult);

        // 사용자가 처음 입력한 고민을 1번째 메시지로 등록하고, 그 뒤에 AI의 괘 분석 첫 답변 배치
        const initialUserMsg: ChatMessageType = {
          id: `user-init-${Date.now()}`,
          sender: 'user',
          content: q,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        };

        setMessages([initialUserMsg, apiRes.firstMessage]);
        setStep('revealed'); // 괘 결과 확인 단계
      }
    } catch (err) {
      console.error(err);
      alert('상담을 시작하는 중 오류가 발생했습니다.');
      setStep('intake');
    } finally {
      setIsLoading(false);
    }
  };

  // 2. 괘 확인 후 본격적인 대화 진입
  const handleProceedToCounsel = () => {
    setStep('counseling');
  };

  // 3. 상담 턴 전송
  const handleSendMessage = async (text: string) => {
    if (!text.trim() || isLoading || !castResult) return;

    const userMsg: ChatMessageType = {
      id: `user-${Date.now()}`,
      sender: 'user',
      content: text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);

    try {
      const turnCount = Math.floor(messages.length / 2) + 1;
      const apiRes = await sendConsultationTurnApi(sessionId, text, turnCount, castResult);

      setMessages((prev) => [...prev, apiRes.replyMessage]);

      if (apiRes.isFinal) {
        if (apiRes.journal) {
          setJournal(apiRes.journal);
        }
        setStep('completed');
      }
    } catch (err) {
      console.error(err);
      setMessages((prev) => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          sender: 'system',
          content: '답변을 불러오는 중 문제가 발생했습니다. 다시 시도해 주세요.',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  // 상담 리셋
  const handleRestart = () => {
    setStep('intake');
    setQuestion('');
    setCastResult(null);
    setMessages([]);
    setJournal(null);
    setSessionId('');
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
              <h1 className="text-base font-serif font-semibold tracking-wide text-stone-100">
                주역 심층 상담 <span className="text-xs font-sans text-amber-500/80 font-normal">I-Ching Oracle</span>
              </h1>
              <p className="text-[10px] text-stone-500 font-light">
                변화의 지혜를 거울삼는 성찰 대화
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* 웰컴 크레딧 배지 */}
            <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-amber-500/10 border border-amber-500/20 text-[11px] text-amber-300 font-medium">
              <Sparkles className="w-3.5 h-3.5 text-amber-400" />
              <span>50 크레딧 보유</span>
            </div>

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
                  onChange={(e) => setQuestion(e.target.value)}
                  placeholder="예: 새로운 이직 기회가 찾아왔는데, 지금 떠나는 것이 좋은 선택일지 마음이 복잡합니다..."
                  className="w-full bg-stone-950/60 border border-stone-800/80 rounded-xl p-3.5 text-sm text-stone-100 placeholder-stone-600 focus:outline-none focus:border-amber-500/50 resize-none transition"
                />

                <div className="mt-4 flex justify-end">
                  <button
                    onClick={() => handleStartConsultation()}
                    disabled={!question.trim() || isLoading}
                    className="w-full sm:w-auto px-6 py-3 rounded-xl bg-amber-600 hover:bg-amber-500 disabled:bg-stone-800 text-stone-950 disabled:text-stone-600 font-medium text-sm transition-all flex items-center justify-center gap-2 cursor-pointer disabled:cursor-not-allowed shadow-lg shadow-amber-950/30"
                  >
                    <span>마음을 모아 괘 도출하기</span>
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

          {/* 3. 괘 도출 결과 확인 단계 (Revealed) */}
          {step === 'revealed' && castResult && (
            <motion.div
              key="revealed"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, y: -20 }}
              className="my-auto py-6"
            >
              <HexagramCard
                castResult={castResult}
                onProceedToCounsel={handleProceedToCounsel}
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
              <JournalSummaryCard journal={journal} onRestart={handleRestart} />
            </motion.div>
          )}
        </AnimatePresence>
      </main>

      {/* 푸터 */}
      <footer className="border-t border-stone-900 py-3 text-center text-[11px] text-stone-600 font-light">
        <span>© 2026 주역 AI 상담 서비스 · 본 서비스는 의학적·심리적 진단을 제공하지 않으며 자율적 성찰을 지원합니다.</span>
        <span className="mt-1 block text-stone-700">
          주역 원문, 정전(程傳) 및 본의(本義) 주석 텍스트: Kanseki Repository (漢籍リポジトリ),
          교토대학 인문과학연구소. CC BY-SA 4.0.
        </span>
      </footer>
    </div>
  );
}
