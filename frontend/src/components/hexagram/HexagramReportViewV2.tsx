'use client';

import React, { useState } from 'react';
import { motion } from 'framer-motion';
import {
  Sparkles,
  Copy,
  Check,
  ArrowRight,
  Compass,
  Lightbulb,
  ShieldCheck,
  Calendar,
  Layers,
  HelpCircle,
  Clock,
  Target,
  FileDown,
} from 'lucide-react';
import { PreCounselingReportV2, ReportSourceRole, LineInfo } from '../../types/iching';
import { renderReportV2Markdown } from './reportMarkdown';
import { HexagramSymbol } from './HexagramSymbol';

interface HexagramReportViewV2Props {
  report: PreCounselingReportV2;
  isLoggedIn?: boolean;
  onProceedToCounsel: () => void;
}

const POSITION_NAMES: Record<number, string> = {
  1: '초효',
  2: '2효',
  3: '3효',
  4: '4효',
  5: '5효',
  6: '상효',
};

const ROLE_LABELS: Record<ReportSourceRole, string> = {
  primary: '주 근거',
  auxiliary: '보조 근거',
  background: '배경',
  body_use: '체용 참작',
  supplement: '보충 (대상전)',
  annotation: '고전 주석',
};

const ROLE_COLORS: Record<ReportSourceRole, string> = {
  primary: 'text-amber-400 border-amber-500/40 bg-amber-500/10',
  auxiliary: 'text-sky-400 border-sky-500/40 bg-sky-500/10',
  background: 'text-stone-400 border-stone-600/40 bg-stone-800/40',
  body_use: 'text-purple-400 border-purple-500/40 bg-purple-500/10',
  supplement: 'text-emerald-400 border-emerald-500/40 bg-emerald-500/10',
  annotation: 'text-amber-300 border-amber-400/30 bg-stone-900/80',
};

export const HexagramReportViewV2: React.FC<HexagramReportViewV2Props> = ({
  report,
  isLoggedIn = true,
  onProceedToCounsel,
}) => {
  const [copied, setCopied] = useState(false);

  const { narrative, academic_details, generation_metadata } = report;
  const { casting, focus_rule, sources } = academic_details;
  const task = narrative.micro_action_task;

  // 본괘 라인 -> LineInfo 변환
  const originalLineInfos: LineInfo[] = casting.lines.map((l) => ({
    position: l.position,
    value: l.value,
    isYang: l.value === 7 || l.value === 9,
    isChanging: l.is_changing,
  }));

  // 지괘 라인 계산 (6: 음->양(7), 9: 양->음(8))
  const transformedLineInfos: LineInfo[] = originalLineInfos.map((l) => {
    if (l.value === 6) return { ...l, isYang: true, isChanging: false, value: 7 as const };
    if (l.value === 9) return { ...l, isYang: false, isChanging: false, value: 8 as const };
    return { ...l, isChanging: false };
  });

  const handleCopyMarkdown = async () => {
    try {
      const md = renderReportV2Markdown(report);
      await navigator.clipboard.writeText(md);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (e) {
      console.error('마크다운 복사 실패:', e);
    }
  };

  const handleDownloadMarkdown = () => {
    try {
      const md = renderReportV2Markdown(report);
      const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `iching-report-v2-${casting.original_name}.md`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (e) {
      console.error('파일 다운로드 실패:', e);
    }
  };

  return (
    <div className="w-full max-w-3xl mx-auto space-y-6 sm:space-y-8 py-4">
      {/* 1. 최상단 헤드라인 인용구 */}
      <motion.div
        initial={{ opacity: 0, y: 15 }}
        animate={{ opacity: 1, y: 0 }}
        className="rounded-3xl border border-amber-500/30 bg-gradient-to-br from-amber-500/10 via-stone-900/90 to-stone-950 p-6 sm:p-8 text-stone-100 shadow-2xl backdrop-blur-sm relative overflow-hidden"
      >
        <div className="flex items-center justify-between gap-4 mb-4">
          <div className="flex items-center gap-2 text-amber-400 text-xs sm:text-sm font-medium tracking-wide">
            <Sparkles className="w-4 h-4 text-amber-400 shrink-0" />
            <span>오늘 주역이 당신에게 건네는 통찰</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleCopyMarkdown}
              className="inline-flex items-center gap-1.5 rounded-xl border border-stone-700/80 bg-stone-900/80 px-3 py-1.5 text-xs text-stone-300 hover:text-stone-100 hover:border-amber-500/40 transition"
              title="마크다운 보고서 복사"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
              <span>{copied ? '복사 완료' : 'MD 복사'}</span>
            </button>
            <button
              onClick={handleDownloadMarkdown}
              className="inline-flex items-center gap-1.5 rounded-xl border border-stone-700/80 bg-stone-900/80 px-3 py-1.5 text-xs text-stone-300 hover:text-stone-100 hover:border-amber-500/40 transition"
              title="마크다운 파일 다운로드"
            >
              <FileDown className="w-3.5 h-3.5" />
              <span>저장</span>
            </button>
          </div>
        </div>

        <blockquote className="border-l-4 border-amber-400/80 pl-4 py-1 text-lg sm:text-xl font-serif font-semibold text-amber-100/95 leading-relaxed">
          &ldquo;{narrative.headline_metaphor}&rdquo;
        </blockquote>
      </motion.div>

      {/* 2. 도출된 괘상 비주얼 카드 (본괘 & 지괘) */}
      <motion.div
        initial={{ opacity: 0, y: 15 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.03 }}
        className="grid grid-cols-1 sm:grid-cols-2 gap-4"
      >
        {/* 본괘 시각화 카드 */}
        <div className="rounded-3xl border border-amber-500/40 bg-stone-900/90 p-5 flex items-center gap-5 shadow-xl">
          <HexagramSymbol lines={originalLineInfos} size="sm" />
          <div className="space-y-1">
            <span className="text-xs font-semibold text-amber-400 tracking-wider uppercase">
              도출된 본괘
            </span>
            <div className="text-lg font-serif font-bold text-stone-100">
              {casting.original_name}
            </div>
            <div className="text-xs text-stone-400">
              하괘 {casting.original_lower_trigram} · 상괘 {casting.original_upper_trigram}
            </div>
          </div>
        </div>

        {/* 지괘 시각화 카드 */}
        {casting.has_transformation && casting.transformed_name ? (
          <div className="rounded-3xl border border-stone-700/80 bg-stone-900/90 p-5 flex items-center gap-5 shadow-xl">
            <HexagramSymbol lines={transformedLineInfos} size="sm" />
            <div className="space-y-1">
              <span className="text-xs font-semibold text-sky-400 tracking-wider uppercase">
                변화된 지괘
              </span>
              <div className="text-lg font-serif font-bold text-stone-100">
                {casting.transformed_name}
              </div>
              <div className="text-xs text-stone-400">
                동효: {casting.changing_lines.map((p) => `${p}효`).join(', ')}
              </div>
            </div>
          </div>
        ) : (
          <div className="rounded-3xl border border-stone-800 bg-stone-950/40 p-5 flex items-center justify-center text-center shadow-lg">
            <div className="space-y-1">
              <span className="text-xs font-semibold text-stone-500 tracking-wider uppercase">
                변화의 흐름
              </span>
              <div className="text-sm font-serif text-stone-400">
                변효가 없는 굳건한 불변괘(不變卦)
              </div>
              <div className="text-xs text-stone-500">
                본래 괘상의 흐름을 온전히 따릅니다.
              </div>
            </div>
          </div>
        )}
      </motion.div>

      {/* 3. 섹션 1: 당신이 지나가는 계절의 이름 */}
      <motion.section
        initial={{ opacity: 0, y: 15 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.05 }}
        className="rounded-3xl border border-stone-800/80 bg-stone-900/70 p-6 sm:p-8 space-y-4 shadow-xl"
      >
        <div className="flex items-center gap-2.5 text-stone-200">
          <Calendar className="w-5 h-5 text-amber-400 shrink-0" />
          <h2 className="text-base sm:text-lg font-serif font-bold text-stone-100">
            1. 당신이 지나가는 계절의 이름 (본괘: {casting.original_name})
          </h2>
        </div>

        <p className="text-sm sm:text-base leading-relaxed text-stone-300 whitespace-pre-line">
          {narrative.emotional_context.validation}
        </p>

        {/* 함께 살펴볼 가설 (확정 사실이 아님을 명시적으로 구분) */}
        {narrative.emotional_context.pattern_hypothesis && (
          <div className="mt-4 rounded-2xl border border-amber-500/20 bg-amber-500/5 p-4 text-xs sm:text-sm text-stone-300 space-y-1">
            <div className="flex items-center gap-2 text-amber-400/90 font-medium">
              <HelpCircle className="w-4 h-4 shrink-0" />
              <span>함께 살펴볼 가설입니다</span>
            </div>
            <p className="pl-6 italic text-stone-300/90 leading-relaxed">
              {narrative.emotional_context.pattern_hypothesis}
            </p>
          </div>
        )}
      </motion.section>

      {/* 3. 섹션 2: 생각의 덫에서 벗어나기 */}
      <motion.section
        initial={{ opacity: 0, y: 15 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="rounded-3xl border border-stone-800/80 bg-stone-900/70 p-6 sm:p-8 space-y-5 shadow-xl"
      >
        <div className="flex items-center gap-2.5 text-stone-200">
          <Compass className="w-5 h-5 text-sky-400 shrink-0" />
          <h2 className="text-base sm:text-lg font-serif font-bold text-stone-100">
            2. 생각의 덫에서 벗어나기
          </h2>
        </div>

        {/* thought_observation (있으면 표시) */}
        {narrative.perspective.thought_observation && (
          <div className="rounded-2xl border border-stone-800 bg-stone-950/40 p-4 text-xs sm:text-sm text-stone-400 leading-relaxed">
            {narrative.perspective.thought_observation}
          </div>
        )}

        <div className="space-y-4">
          {/* 고전이 말하는 바 (절대 applied_reading과 합치지 않음) */}
          <div className="rounded-2xl border border-sky-500/20 bg-sky-950/10 p-4 sm:p-5 space-y-1.5">
            <span className="text-xs font-semibold text-sky-400 tracking-wide uppercase">
              고전이 말하는 바
            </span>
            <p className="text-sm sm:text-base leading-relaxed text-stone-200 font-serif">
              {narrative.perspective.classical_reading}
            </p>
          </div>

          {/* 이번 사연에 옮기면 */}
          <div className="rounded-2xl border border-stone-800 bg-stone-950/60 p-4 sm:p-5 space-y-1.5">
            <span className="text-xs font-semibold text-amber-400 tracking-wide uppercase">
              이번 사연에 옮기면
            </span>
            <p className="text-sm sm:text-base leading-relaxed text-stone-300">
              {narrative.perspective.applied_reading}
            </p>
          </div>

          {/* 새로운 시선 (alternative_perspective) */}
          <div className="rounded-2xl border border-emerald-500/20 bg-emerald-950/10 p-4 sm:p-5 space-y-1.5">
            <span className="text-xs font-semibold text-emerald-400 tracking-wide uppercase">
              새로운 시선
            </span>
            <p className="text-sm sm:text-base leading-relaxed text-stone-200">
              {narrative.perspective.alternative_perspective}
            </p>
          </div>
        </div>
      </motion.section>

      {/* 4. 섹션 3: 나아갈 삶의 가치와 경고등 */}
      <motion.section
        initial={{ opacity: 0, y: 15 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15 }}
        className="rounded-3xl border border-stone-800/80 bg-stone-900/70 p-6 sm:p-8 space-y-4 shadow-xl"
      >
        <div className="flex items-center gap-2.5 text-stone-200">
          <Lightbulb className="w-5 h-5 text-amber-400 shrink-0" />
          <h2 className="text-base sm:text-lg font-serif font-bold text-stone-100">
            3. 나아갈 삶의 가치와 경고등
          </h2>
        </div>

        {/* proposed_value가 null이면 아예 표시하지 않음 ("미정" 대체 금지) */}
        {narrative.value_direction.proposed_value && (
          <div className="inline-flex items-center gap-2 rounded-xl border border-amber-500/40 bg-amber-500/10 px-3.5 py-1.5 text-xs sm:text-sm font-semibold text-amber-300">
            <span>지켜볼 가치:</span>
            <span className="text-stone-100">{narrative.value_direction.proposed_value}</span>
          </div>
        )}

        <p className="text-sm sm:text-base leading-relaxed text-stone-300">
          {narrative.value_direction.rationale}
        </p>

        {/* 선택할 때 점검할 조건 (목록) */}
        {narrative.value_direction.conditions_to_check.length > 0 && (
          <div className="mt-4 rounded-2xl border border-stone-800/90 bg-stone-950/50 p-4 sm:p-5 space-y-2.5">
            <h3 className="text-xs sm:text-sm font-semibold text-stone-200 flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-amber-400" />
              <span>선택할 때 점검할 조건</span>
            </h3>
            <ul className="space-y-1.5 pl-2">
              {narrative.value_direction.conditions_to_check.map((cond, idx) => (
                <li key={idx} className="text-xs sm:text-sm text-stone-400 flex items-start gap-2">
                  <span className="text-amber-500/80 shrink-0 mt-1">•</span>
                  <span className="leading-relaxed">{cond}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </motion.section>

      {/* 5. 섹션 4: 오늘 나를 구하는 N분 행동 */}
      <motion.section
        initial={{ opacity: 0, y: 15 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="rounded-3xl border border-emerald-500/30 bg-gradient-to-br from-emerald-950/20 via-stone-900/90 to-stone-950 p-6 sm:p-8 space-y-5 shadow-xl"
      >
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <div className="flex items-center gap-2.5 text-stone-200">
            <Target className="w-5 h-5 text-emerald-400 shrink-0" />
            <h2 className="text-base sm:text-lg font-serif font-bold text-stone-100">
              4. 오늘 나를 구하는 {task.duration_minutes}분 행동
            </h2>
          </div>
          <span className="inline-flex items-center gap-1.5 text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/30 px-3 py-1 rounded-full">
            <Clock className="w-3.5 h-3.5" />
            약 {task.duration_minutes}분 소요
          </span>
        </div>

        <div className="space-y-3">
          <div className="text-base sm:text-lg font-serif font-semibold text-emerald-200">
            🎯 {task.title}
          </div>
          <div className="text-xs sm:text-sm text-stone-400">
            <strong className="text-stone-300">언제:</strong> {task.when}
          </div>
        </div>

        {/* 단계별 행동 목록 (체크박스/완료 버튼 없음 - 읽기 전용) */}
        <div className="space-y-2 rounded-2xl border border-stone-800 bg-stone-950/60 p-4 sm:p-5">
          <div className="text-xs font-semibold text-stone-400 tracking-wider uppercase mb-2">
            행동 단계
          </div>
          <ol className="space-y-2">
            {task.steps.map((step, idx) => (
              <li key={idx} className="flex items-start gap-3 text-xs sm:text-sm text-stone-300">
                <span className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-emerald-500/20 text-emerald-400 font-mono text-xs font-bold">
                  {idx + 1}
                </span>
                <span className="leading-relaxed mt-0.5">{step}</span>
              </li>
            ))}
          </ol>
        </div>

        <div className="space-y-2 text-xs sm:text-sm text-stone-400">
          <div>
            <strong className="text-stone-300">끝난 것으로 볼 기준:</strong>{' '}
            <span>{task.completion_criterion}</span>
          </div>

          {/* smaller_alternative가 null이면 아예 행 생략 */}
          {task.smaller_alternative && (
            <div>
              <strong className="text-stone-300">더 작게 하려면:</strong>{' '}
              <span>{task.smaller_alternative}</span>
            </div>
          )}
        </div>

        {/* 필수 제안 문구 (다짐/서약/약속 용어 사용 금지) */}
        <div className="pt-2 text-center text-xs text-stone-400 italic">
          *제안입니다. 하실지는 직접 정하시면 됩니다.*
        </div>
      </motion.section>

      {/* 6. 하단 근거 패널: 고전 수리 검증 및 원전 근거 (기본 닫힘, 키보드 접근성 완비) */}
      <motion.section
        initial={{ opacity: 0, y: 15 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.25 }}
        className="rounded-3xl border border-stone-800 bg-stone-950/80 shadow-lg overflow-hidden"
      >
        <details className="group">
          <summary
            className="cursor-pointer select-none p-6 sm:p-7 flex items-center justify-between gap-4 text-stone-300 hover:text-stone-100 hover:bg-stone-900/50 transition focus:outline-none focus:ring-2 focus:ring-amber-500/50"
            aria-label="고전 수리 검증 및 원전 근거 열고 닫기"
          >
            <div className="flex items-center gap-3">
              <Layers className="w-5 h-5 text-amber-400 shrink-0" />
              <span className="font-serif font-bold text-sm sm:text-base text-stone-200">
                📜 고전 수리 검증 및 원전 근거 보기
              </span>
            </div>
            <span className="text-xs text-stone-500 group-open:rotate-180 transition-transform duration-200">
              ▼
            </span>
          </summary>

          <div className="px-6 sm:px-8 pb-8 pt-2 space-y-6 text-xs sm:text-sm text-stone-300 border-t border-stone-800/80">
            {/* 1. 점서 예식 및 수리 도출 */}
            <div className="space-y-2">
              <h4 className="font-semibold text-stone-200 text-sm flex items-center gap-2">
                <span>1. 점서 예식 및 수리 도출</span>
              </h4>
              <ul className="space-y-1.5 pl-3 border-l-2 border-stone-800">
                <li>
                  <strong>점서 예식:</strong> 재삼독(再三瀆) 원칙에 따라 이 세션의 괘는 한 번 도출한 뒤 다시 뽑지 않습니다.
                </li>
                <li>
                  <strong>도출 수리:</strong>{' '}
                  <span className="font-mono text-stone-400">
                    {casting.lines
                      .map((l) => `${POSITION_NAMES[l.position] || `${l.position}효`}(${l.value})`)
                      .join(' ➔ ')}
                  </span>
                </li>
                <li>
                  <strong>본괘:</strong> {casting.original_name} (하괘 {casting.original_lower_trigram}, 상괘 {casting.original_upper_trigram})
                </li>
                <li>
                  <strong>지괘:</strong>{' '}
                  {casting.has_transformation && casting.transformed_name
                    ? casting.transformed_name
                    : '없음 (동효가 없는 불변괘입니다)'}
                </li>
              </ul>
            </div>

            {/* 2. 고변점 판정 규칙 */}
            <div className="space-y-2">
              <h4 className="font-semibold text-stone-200 text-sm flex items-center gap-2">
                <span>2. 고변점(考變占) 판정 규칙</span>
              </h4>
              <ul className="space-y-1.5 pl-3 border-l-2 border-stone-800">
                <li>
                  <strong>변효 개수:</strong> {focus_rule.changing_count}개
                  {casting.changing_lines.length > 0
                    ? ` (위치 ${casting.changing_lines.map((p) => `${p}효`).join(', ')})`
                    : ' (불변괘)'}
                </li>
                <li>
                  <strong>해석 원칙:</strong> {focus_rule.description_ko}
                </li>
                {focus_rule.body_use_note_ko && (
                  <li>
                    <strong>체용 참작:</strong> {focus_rule.body_use_note_ko}
                  </li>
                )}
                <li>
                  <strong>규칙 판본:</strong> <span className="font-mono text-stone-400">{focus_rule.rule_version}</span>
                </li>
              </ul>
            </div>

            {/* 3. 고전 원문 및 번역 */}
            <div className="space-y-3">
              <h4 className="font-semibold text-stone-200 text-sm">
                3. 고전 원문 및 번역
              </h4>
              <div className="space-y-3">
                {sources.map((src) => {
                  const roleLabel = ROLE_LABELS[src.role] || src.role;
                  const roleColor = ROLE_COLORS[src.role] || 'text-stone-400 border-stone-700 bg-stone-900';
                  const lineLabel =
                    src.role === 'supplement'
                      ? '대상전'
                      : src.line_number === null
                      ? '괘사'
                      : src.line_number === 7
                      ? '용구/용육'
                      : `${src.line_number}효`;

                  if (src.role === 'annotation') {
                    return (
                      <div key={src.id} className="rounded-xl border border-stone-800 bg-stone-900/60 p-3.5 space-y-1.5">
                        <div className="flex items-center gap-2">
                          <span className={`px-2 py-0.5 rounded text-[11px] font-semibold border ${roleColor}`}>
                            {roleLabel}
                          </span>
                          <span className="font-medium text-stone-200">
                            {src.annotation_source || '출처 미상'}
                          </span>
                        </div>
                        <p className="text-xs sm:text-sm text-stone-300 leading-relaxed pl-2 border-l-2 border-amber-500/30">
                          {src.annotation}
                        </p>
                      </div>
                    );
                  }

                  return (
                    <div key={src.id} className="rounded-xl border border-stone-800 bg-stone-900/60 p-3.5 space-y-2">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className={`px-2 py-0.5 rounded text-[11px] font-semibold border ${roleColor}`}>
                          {roleLabel}
                        </span>
                        <span className="font-medium text-stone-200">
                          {src.hexagram_name} {lineLabel}
                        </span>
                      </div>
                      <div className="space-y-1 text-xs sm:text-sm pl-2 border-l-2 border-stone-700">
                        <div>
                          <strong className="text-stone-400">원문:</strong>{' '}
                          <span className="text-stone-200 font-serif">{src.classical_text}</span>
                        </div>
                        <div>
                          <strong className="text-stone-400">번역:</strong>{' '}
                          <span className={src.classical_translation ? 'text-stone-300' : 'text-stone-500 italic'}>
                            {src.classical_translation || '(확인된 번역 없음)'}
                          </span>
                        </div>
                        {src.locator && (
                          <div className="text-[11px] text-stone-500">
                            <strong>출처:</strong> {src.locator}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* 4. 생성 정보 */}
            <div className="space-y-1 pt-2 border-t border-stone-800/60 text-[11px] sm:text-xs text-stone-500">
              <h4 className="font-semibold text-stone-400">4. 생성 정보</h4>
              <div>생성 시각: {generation_metadata.generated_at}</div>
              <div>모델: {generation_metadata.model || '(미확인)'}</div>
              <div>프롬프트 판본: {generation_metadata.prompt_version}</div>
              <div>근거 지문: {generation_metadata.evidence_snapshot_hash.slice(0, 16)}</div>
            </div>
          </div>
        </details>
      </motion.section>

      {/* 7. 최하단 상담 진입 CTA 버튼 */}
      <motion.div
        initial={{ opacity: 0, y: 15 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
        className="pt-6 border-t border-stone-800 flex flex-col sm:flex-row items-center justify-between gap-5"
      >
        <span className="text-xs sm:text-sm text-stone-400 font-light text-center sm:text-left">
          {isLoggedIn
            ? '사전 분석 리포트를 숙고하신 후, 수석 AI 상담사와 1:1 심층 질의응답을 진행하세요.'
            : '간편가입 시 50 웰컴 크레딧(대화 5회분)이 즉시 지급되어, 이 괘를 바탕으로 AI와 바로 상담을 이어갈 수 있습니다.'}
        </span>

        <button
          onClick={onProceedToCounsel}
          className="w-full sm:w-auto px-8 py-4 rounded-2xl bg-gradient-to-r from-amber-500 to-amber-400 hover:from-amber-400 hover:to-amber-300 text-stone-950 font-bold text-base transition-all shadow-xl shadow-amber-950/60 flex items-center justify-center gap-2.5 cursor-pointer active:scale-[0.98] shrink-0"
        >
          <span>{isLoggedIn ? '이 관점으로 상담 이어가기' : '50 크레딧 받고 심층 상담 시작하기'}</span>
          <ArrowRight className="w-5 h-5" />
        </button>
      </motion.div>
    </div>
  );
};
