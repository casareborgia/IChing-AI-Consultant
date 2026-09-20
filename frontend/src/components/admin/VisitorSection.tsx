'use client';

import React from 'react';
import { VisitorStats } from '@/lib/api';

/**
 * 막대 높이 비율. 0으로 나누지 않는다.
 *
 * 값이 0이면 0을 돌려준다 — 방문이 없던 날에 최소 높이 막대가 서면 "조금 있었다"로
 * 읽힌다. 0이 아닌 값은 최소 2%를 줘서 막대가 아예 사라지지 않게 한다.
 */
function ratio(value: number, max: number): number {
  if (max <= 0 || value <= 0) return 0;
  return Math.max(2, Math.round((value / max) * 100));
}

const DEVICE_LABELS: Record<string, string> = {
  mobile: '모바일',
  tablet: '태블릿',
  desktop: 'PC',
  unknown: '미확인',
};

/**
 * 방문자 및 재방문 현황.
 *
 * 자체 방문 로그(site_visits) 집계다. Vercel Analytics와 숫자가 다를 수 있다 —
 * 이쪽은 30분 세션 병합 기준의 방문(visit)을 세고, 저쪽은 페이지뷰를 센다.
 */
export function VisitorSection({ visitors }: { visitors: VisitorStats }) {
  if (!visitors?.enabled) {
    return (
      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-stone-400 uppercase tracking-wider">방문자 및 재방문 현황</h2>
        <div className="p-5 rounded-2xl bg-stone-900/70 border border-stone-800 text-sm text-stone-400 space-y-2">
          <div className="text-stone-300 font-medium">방문 수집이 비활성 상태입니다.</div>
          <p className="text-xs">
            {visitors?.reason || '수집 스위치가 꺼져 있습니다.'}
          </p>
          <p className="text-xs text-stone-500">
            개인정보처리방침에 방문 기록 수집을 고지한 뒤, 백엔드 환경변수{' '}
            <code className="px-1 rounded bg-stone-950 text-amber-400/90">VISITOR_ANALYTICS_ENABLED=true</code> 와{' '}
            <code className="px-1 rounded bg-stone-950 text-amber-400/90">VISITOR_ID_PEPPER</code>(16자 이상)를 설정하면
            집계가 시작됩니다.
          </p>
        </div>
      </section>
    );
  }

  const today = visitors.today;
  const week = visitors.last_7d;
  const month = visitors.last_30d;
  const total = visitors.total;
  const trend = visitors.trend || [];
  const buckets = visitors.revisit_buckets || [];
  const trendMax = Math.max(1, ...trend.map((d) => d.visits));
  const bucketTotal = buckets.reduce((acc, b) => acc + b.visitors, 0);
  const memberVisits = visitors.member_visits || 0;
  const anonymousVisits = visitors.anonymous_visits || 0;
  const visitsSum = memberVisits + anonymousVisits;

  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-sm font-semibold text-stone-400 uppercase tracking-wider">방문자 및 재방문 현황</h2>
        <p className="text-[11px] text-stone-500 font-mono">
          기준 시간대 {visitors.timezone || 'Asia/Seoul'} · 30분 이내 재접속은 같은 방문으로 집계
        </p>
      </div>
      <div className="text-[11px] text-stone-500 space-y-0.5">
        <p>* 동일 기간 첫 방문 후 재방문한 이용자는 신규와 재방문 모두에 집계되므로 둘의 합이 순 방문자수와 일치하지 않을 수 있습니다.</p>
        <p>* 본 수치는 1st-party 가명 로그 집계치이며 조작 방어가 완전히 보장된 값이 아닙니다.</p>
      </div>

      {/* 방문자 KPI */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
        <div className="p-4 rounded-2xl bg-stone-900/70 border border-stone-800 hover:border-stone-700 transition space-y-1">
          <div className="text-xs text-stone-400 font-medium">오늘 방문자</div>
          <div className="text-2xl font-bold text-sky-300 flex items-baseline space-x-1">
            <span>{today?.unique_visitors ?? 0}</span>
            <span className="text-xs text-stone-400 font-normal">명</span>
          </div>
          <div className="text-[11px] text-stone-400 font-mono">방문 {today?.visits ?? 0}회</div>
        </div>

        <div className="p-4 rounded-2xl bg-stone-900/70 border border-stone-800 hover:border-stone-700 transition space-y-1">
          <div className="text-xs text-stone-400 font-medium">오늘 신규 / 재방문</div>
          <div className="text-2xl font-bold text-stone-100 flex items-baseline space-x-1">
            <span className="text-emerald-400">{today?.new_visitors ?? 0}</span>
            <span className="text-sm text-stone-500">/</span>
            <span className="text-amber-300">{today?.returning_visitors ?? 0}</span>
            <span className="text-xs text-stone-400 font-normal">명</span>
          </div>
          <div className="text-[11px] text-stone-400 font-mono">재방문율 {today?.revisit_rate_pct ?? 0}%</div>
        </div>

        <div className="p-4 rounded-2xl bg-stone-900/70 border border-stone-800 hover:border-stone-700 transition space-y-1">
          <div className="text-xs text-stone-400 font-medium">최근 7일 방문자</div>
          <div className="text-2xl font-bold text-sky-300 flex items-baseline space-x-1">
            <span>{week?.unique_visitors ?? 0}</span>
            <span className="text-xs text-stone-400 font-normal">명</span>
          </div>
          <div className="text-[11px] text-stone-400 font-mono">
            방문 {week?.visits ?? 0}회 · 재방문율 {week?.revisit_rate_pct ?? 0}%
          </div>
        </div>

        <div className="p-4 rounded-2xl bg-stone-900/70 border border-stone-800 hover:border-stone-700 transition space-y-1">
          <div className="text-xs text-stone-400 font-medium">최근 30일 방문자</div>
          <div className="text-2xl font-bold text-sky-300 flex items-baseline space-x-1">
            <span>{month?.unique_visitors ?? 0}</span>
            <span className="text-xs text-stone-400 font-normal">명</span>
          </div>
          <div className="text-[11px] text-stone-400 font-mono">
            방문 {month?.visits ?? 0}회 · 재방문율 {month?.revisit_rate_pct ?? 0}%
          </div>
        </div>

        <div className="p-4 rounded-2xl bg-stone-900/70 border border-stone-800 hover:border-stone-700 transition space-y-1">
          <div className="text-xs text-stone-400 font-medium">보존기간 내 누적</div>
          <div className="text-2xl font-bold text-stone-100 flex items-baseline space-x-1">
            <span>{(total?.unique_visitors ?? 0).toLocaleString()}</span>
            <span className="text-xs text-stone-400 font-normal">명</span>
          </div>
          <div className="text-[11px] text-stone-400 font-mono">
            1인당 평균 {total?.avg_visits_per_visitor ?? 0}회 · 최다 {total?.max_visits_per_visitor ?? 0}회
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* 14일 방문 추이 */}
        <div className="lg:col-span-2 p-5 rounded-2xl bg-stone-900/50 border border-stone-800 space-y-4">
          <div className="flex items-baseline justify-between">
            <h3 className="text-sm font-bold text-stone-200">최근 14일 방문 추이</h3>
            <div className="flex items-center gap-3 text-[11px] text-stone-400">
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-sm bg-sky-500/80" /> 방문
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-sm bg-emerald-500/80" /> 신규 방문자
              </span>
            </div>
          </div>

          {trend.length === 0 ? (
            <div className="py-10 text-center text-xs text-stone-500">아직 집계된 방문이 없습니다.</div>
          ) : (
            <div className="flex items-end justify-between gap-1 h-40">
              {trend.map((day) => (
                <div key={day.date} className="flex-1 flex flex-col items-center justify-end gap-1 group">
                  <div
                    className="w-full flex items-end justify-center gap-[2px] h-32"
                    title={`${day.date} · 방문 ${day.visits}회 / 방문자 ${day.unique_visitors}명 / 신규 ${day.new_visitors}명`}
                  >
                    <div
                      className="w-1/2 rounded-t bg-sky-500/70 group-hover:bg-sky-400 transition"
                      style={{ height: `${ratio(day.visits, trendMax)}%` }}
                    />
                    <div
                      className="w-1/2 rounded-t bg-emerald-500/60 group-hover:bg-emerald-400 transition"
                      style={{ height: `${ratio(day.new_visitors, trendMax)}%` }}
                    />
                  </div>
                  <span className="text-[9px] text-stone-500 font-mono">{day.date.slice(5)}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* 재방문 횟수 분포 */}
        <div className="p-5 rounded-2xl bg-stone-900/50 border border-stone-800 space-y-4">
          <div>
            <h3 className="text-sm font-bold text-stone-200">재방문 횟수 분포</h3>
            <p className="text-[11px] text-stone-500">최근 180일 보존분 기준 · 누적 방문자 {bucketTotal.toLocaleString()}명</p>
          </div>

          <div className="space-y-2.5">
            {buckets.map((bucket) => {
              const pct = bucketTotal > 0 ? Math.round((bucket.visitors / bucketTotal) * 100) : 0;
              return (
                <div key={bucket.label} className="space-y-1">
                  <div className="flex items-baseline justify-between text-xs">
                    <span className="text-stone-300">{bucket.label}</span>
                    <span className="font-mono text-stone-400">
                      {bucket.visitors.toLocaleString()}명 <span className="text-stone-500">({pct}%)</span>
                    </span>
                  </div>
                  <div className="h-2 rounded-full bg-stone-950 overflow-hidden">
                    <div className="h-full rounded-full bg-amber-500/70" style={{ width: `${pct}%` }} />
                  </div>
                </div>
              );
            })}
          </div>

          <div className="pt-3 border-t border-stone-800 space-y-2 text-[11px] text-stone-400 font-mono">
            <div className="flex justify-between">
              <span>회원 방문</span>
              <span className="text-stone-300">
                {memberVisits.toLocaleString()}회
                {visitsSum > 0 && ` (${Math.round((memberVisits / visitsSum) * 100)}%)`}
              </span>
            </div>
            <div className="flex justify-between">
              <span>비회원 방문</span>
              <span className="text-stone-300">{anonymousVisits.toLocaleString()}회</span>
            </div>
            {(visitors.devices || []).map((d) => (
              <div key={d.device} className="flex justify-between">
                <span>{DEVICE_LABELS[d.device] || d.device} (30일)</span>
                <span className="text-stone-300">{d.visits.toLocaleString()}회</span>
              </div>
            ))}
          </div>

          {(visitors.top_referrers || []).length > 0 && (
            <div className="pt-3 border-t border-stone-800 space-y-1.5">
              <div className="text-[11px] text-stone-400 font-medium">외부 유입 출처 (30일)</div>
              {(visitors.top_referrers || []).map((r) => (
                <div key={r.host} className="flex justify-between text-[11px] font-mono">
                  <span className="text-stone-300 truncate max-w-[70%]" title={r.host}>{r.host}</span>
                  <span className="text-stone-400">{r.visits.toLocaleString()}회</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
