'use client';

import React, { useEffect, useState, useCallback } from 'react';
import Link from 'next/link';
import { useAuth } from '@/context/AuthContext';
import { fetchAdminDashboardApi, postGrantCreditApi, AdminDashboardData } from '@/lib/api';
import { VisitorSection } from '@/components/admin/VisitorSection';

export default function AdminDashboardPage() {
  const { user, session, isLoading: authLoading } = useAuth();
  const [data, setData] = useState<AdminDashboardData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState<boolean>(false);

  // 탭 상태
  const [activeTab, setActiveTab] = useState<'sessions' | 'ledger'>('sessions');

  // 검색 상태
  const [searchUser, setSearchUser] = useState<string>('');

  // 크레딧 지급 모달 상태
  const [selectedUser, setSelectedUser] = useState<{ id: string; email: string | null; credit: number } | null>(null);
  const [grantAmount, setGrantAmount] = useState<number>(100);
  const [grantReason, setGrantReason] = useState<string>('운영자 보너스 지급');
  const [isSubmittingGrant, setIsSubmittingGrant] = useState<boolean>(false);
  const [grantSuccessMsg, setGrantSuccessMsg] = useState<string | null>(null);

  // 관리자 권한 확인 (기본 casareborgia@gmail.com)
  const isOperator = user?.email === 'casareborgia@gmail.com';

  const loadData = useCallback(async (isSilent = false) => {
    if (!session?.access_token) return;
    if (!isSilent) setLoading(true);
    setError(null);
    try {
      const dashboardData = await fetchAdminDashboardApi(session.access_token);
      setData(dashboardData);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '대시보드 데이터를 불러오지 못했습니다.';
      setError(msg);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [session?.access_token]);

  useEffect(() => {
    if (!authLoading && session?.access_token) {
      loadData();
    }
  }, [authLoading, session?.access_token, loadData]);

  const handleRefresh = () => {
    setRefreshing(true);
    loadData(true);
  };

  const handleGrantCredit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!session?.access_token || !selectedUser || grantAmount <= 0) return;

    setIsSubmittingGrant(true);
    setGrantSuccessMsg(null);
    try {
      const res = await postGrantCreditApi(
        session.access_token,
        selectedUser.id,
        grantAmount,
        grantReason
      );
      setGrantSuccessMsg(`✅ ${res.user_email || '사용자'}님에게 ${res.granted_amount}C를 지급했습니다. (새 잔액: ${res.new_balance}C)`);
      setTimeout(() => {
        setSelectedUser(null);
        setGrantSuccessMsg(null);
        handleRefresh();
      }, 1500);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '크레딧 지급에 실패했습니다.';
      alert(msg);
    } finally {
      setIsSubmittingGrant(false);
    }
  };

  // 비로그인 또는 비운영자일 때 화면
  if (!authLoading && (!user || !isOperator)) {
    return (
      <div className="min-h-screen bg-stone-950 text-stone-200 flex flex-col items-center justify-center p-4">
        <div className="max-w-md w-full p-8 rounded-2xl bg-stone-900/80 border border-stone-800 text-center space-y-4">
          <div className="w-12 h-12 mx-auto rounded-full bg-red-950/50 border border-red-800 flex items-center justify-center text-red-400 text-xl">
            🔒
          </div>
          <h1 className="text-xl font-bold text-stone-100">운영자 전용 구역</h1>
          <p className="text-sm text-stone-400">
            해당 페이지는 서비스 운영자 전용 대시보드입니다. 허용된 운영자 계정으로 로그인해 주시기 바랍니다.
          </p>
          <div className="pt-4">
            <Link
              href="/"
              className="inline-block px-5 py-2.5 rounded-xl bg-stone-800 hover:bg-stone-700 text-stone-200 text-sm font-medium transition"
            >
              메인 홈으로 돌아가기
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // 필터링된 유저 목록
  const filteredUsers = (data?.users || []).filter((u) => {
    if (!searchUser) return true;
    const q = searchUser.toLowerCase();
    return (
      (u.email && u.email.toLowerCase().includes(q)) ||
      (u.nickname && u.nickname.toLowerCase().includes(q)) ||
      u.id.toLowerCase().includes(q)
    );
  });

  return (
    <div className="min-h-screen bg-stone-950 text-stone-100 font-sans pb-16">
      {/* 상단 네비게이션 헤더 */}
      <header className="sticky top-0 z-30 border-b border-stone-800/80 bg-stone-950/80 backdrop-blur-md px-6 py-4">
        <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center space-x-3">
            <span className="text-xl">☯️</span>
            <div>
              <div className="flex items-center space-x-2">
                <h1 className="text-lg font-bold text-stone-100">주역 심층 AI 상담 운영 대시보드</h1>
                <span className="px-2 py-0.5 text-xs rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/30 font-medium">
                  OPERATOR
                </span>
              </div>
              <p className="text-xs text-stone-400">
                로그인 계정: <span className="text-stone-300 font-mono">{user?.email}</span>
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-3 text-sm">
            {/* Vercel Analytics 바로가기 버튼 */}
            <a
              href="https://vercel.com/casareborgias-projects/i-ching-ai-consultant/analytics"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-stone-900 border border-stone-700 hover:border-stone-500 text-stone-300 hover:text-white transition"
            >
              <span>📈 Vercel 페이지뷰 (참고)</span>
              <span className="text-xs">↗</span>
            </a>

            {/* 새로고침 버튼 */}
            <button
              onClick={handleRefresh}
              disabled={refreshing || loading}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-stone-900 border border-stone-700 hover:border-stone-500 text-stone-300 hover:text-white transition disabled:opacity-50"
            >
              <span className={refreshing ? 'animate-spin' : ''}>🔄</span>
              <span>새로고침</span>
            </button>

            {/* 메인 홈 링크 */}
            <Link
              href="/"
              className="px-3 py-1.5 rounded-lg bg-amber-500/10 text-amber-300 border border-amber-500/30 hover:bg-amber-500/20 transition font-medium"
            >
              상담 홈으로 이동
            </Link>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 pt-8 space-y-8">
        {/* 에러 표시 */}
        {error && (
          <div className="p-4 rounded-xl bg-red-950/40 border border-red-800/80 text-red-300 text-sm flex items-center justify-between">
            <span>⚠️ {error}</span>
            <button onClick={() => loadData()} className="underline text-red-200 hover:text-white ml-4">
              다시 시도
            </button>
          </div>
        )}

        {/* 로딩 스켈레톤 */}
        {loading && !data && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4 animate-pulse">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="h-28 rounded-2xl bg-stone-900/60 border border-stone-800" />
            ))}
          </div>
        )}

        {/* 1단 - 핵심 KPI 요약 카드 그리드 */}
        {data && (
          <section className="space-y-3">
            <h2 className="text-sm font-semibold text-stone-400 uppercase tracking-wider">서비스 핵심 지표 (KPI)</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
              {/* 총 가입 회원 */}
              <div className="p-4 rounded-2xl bg-stone-900/70 border border-stone-800 hover:border-stone-700 transition space-y-1">
                <div className="text-xs text-stone-400 font-medium">총 가입 회원</div>
                <div className="text-2xl font-bold text-stone-100 flex items-baseline space-x-1">
                  <span>{data.kpi.total_users}</span>
                  <span className="text-xs text-stone-400 font-normal">명</span>
                </div>
                <div className="text-[11px] text-emerald-400/90 font-mono">실시간 DB 활성 유저</div>
              </div>

              {/* 누적 상담 세션 */}
              <div className="p-4 rounded-2xl bg-stone-900/70 border border-stone-800 hover:border-stone-700 transition space-y-1">
                <div className="text-xs text-stone-400 font-medium">누적 상담 세션</div>
                <div className="text-2xl font-bold text-amber-300 flex items-baseline space-x-1">
                  <span>{data.kpi.total_sessions}</span>
                  <span className="text-xs text-stone-400 font-normal">회</span>
                </div>
                <div className="text-[11px] text-stone-400 font-mono">괘 도출 세션</div>
              </div>

              {/* 누적 대화 턴 수 */}
              <div className="p-4 rounded-2xl bg-stone-900/70 border border-stone-800 hover:border-stone-700 transition space-y-1">
                <div className="text-xs text-stone-400 font-medium">총 대화 턴 수</div>
                <div className="text-2xl font-bold text-stone-100 flex items-baseline space-x-1">
                  <span>{data.kpi.total_turns}</span>
                  <span className="text-xs text-stone-400 font-normal">턴</span>
                </div>
                <div className="text-[11px] text-stone-400 font-mono">
                  평균 {(data.kpi.total_sessions > 0 ? (data.kpi.total_turns / data.kpi.total_sessions).toFixed(1) : '0')}턴 / 세션
                </div>
              </div>

              {/* 생성된 회고 저널 */}
              <div className="p-4 rounded-2xl bg-stone-900/70 border border-stone-800 hover:border-stone-700 transition space-y-1">
                <div className="text-xs text-stone-400 font-medium">생성된 회고 저널</div>
                <div className="text-2xl font-bold text-purple-300 flex items-baseline space-x-1">
                  <span>{data.kpi.total_journals}</span>
                  <span className="text-xs text-stone-400 font-normal">건</span>
                </div>
                <div className="text-[11px] text-stone-400 font-mono">저널 카드 발급</div>
              </div>

              {/* 크레딧 유통량 */}
              <div className="p-4 rounded-2xl bg-stone-900/70 border border-stone-800 hover:border-stone-700 transition space-y-1">
                <div className="text-xs text-stone-400 font-medium">크레딧 총 유통량</div>
                <div className="text-2xl font-bold text-amber-400 flex items-baseline space-x-1">
                  <span>{data.kpi.total_credits_in_circulation.toLocaleString()}</span>
                  <span className="text-xs text-stone-400 font-normal">C</span>
                </div>
                <div className="text-[11px] text-stone-400 font-mono">
                  누적 소비: {data.kpi.total_credits_consumed.toLocaleString()}C
                </div>
              </div>

              {/* AI 비용 예산 현황 */}
              <div className="p-4 rounded-2xl bg-stone-900/70 border border-stone-800 hover:border-stone-700 transition space-y-1">
                <div className="text-xs text-stone-400 font-medium">일일 AI 예산 소진</div>
                <div className="text-2xl font-bold text-emerald-400 flex items-baseline space-x-1">
                  <span>${(data.kpi.budget?.daily_cost_usd || 0).toFixed(3)}</span>
                  <span className="text-xs text-stone-400 font-normal">/ ${data.kpi.budget?.daily_limit_usd || 10}</span>
                </div>
                <div className="text-[11px] text-stone-400 font-mono">
                  월간: ${(data.kpi.budget?.monthly_cost_usd || 0).toFixed(2)} / ${(data.kpi.budget?.monthly_limit_usd || 100)}
                </div>
              </div>
            </div>
          </section>
        )}

        {/* 1.5단 - 방문자 및 재방문 현황 */}
        {data && <VisitorSection visitors={data.visitors} />}

        {/* 2단 - 회원 목록 및 크레딧 관리 테이블 */}
        {data && (
          <section className="space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <h2 className="text-base font-bold text-stone-100 flex items-center space-x-2">
                  <span>👥 가입 회원 및 크레딧 현황</span>
                  <span className="text-xs font-normal text-stone-400 font-mono">({filteredUsers.length}명)</span>
                </h2>
                <p className="text-xs text-stone-400">회원별 잔여 크레딧 및 상담 활동을 확인하고 크레딧을 수동 조정할 수 있습니다.</p>
              </div>

              <div className="w-full sm:w-64">
                <input
                  type="text"
                  placeholder="이메일 또는 닉네임 검색..."
                  value={searchUser}
                  onChange={(e) => setSearchUser(e.target.value)}
                  className="w-full px-3 py-1.5 rounded-xl bg-stone-900 border border-stone-800 text-stone-200 text-sm focus:outline-none focus:border-amber-500/50"
                />
              </div>
            </div>

            <div className="overflow-x-auto rounded-2xl border border-stone-800 bg-stone-900/40">
              <table className="w-full text-left text-sm text-stone-300">
                <thead className="bg-stone-900/80 text-xs uppercase text-stone-400 border-b border-stone-800">
                  <tr>
                    <th className="px-4 py-3">회원 이메일</th>
                    <th className="px-4 py-3">닉네임</th>
                    <th className="px-4 py-3">잔여 크레딧</th>
                    <th className="px-4 py-3">상담 세션 수</th>
                    <th className="px-4 py-3">가입일시</th>
                    <th className="px-4 py-3 text-right">관리</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-800/60 font-mono text-xs">
                  {filteredUsers.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="px-4 py-8 text-center text-stone-500">
                        조회된 회원이 없습니다.
                      </td>
                    </tr>
                  ) : (
                    filteredUsers.map((u) => (
                      <tr key={u.id} className="hover:bg-stone-800/30 transition">
                        <td className="px-4 py-3 font-medium text-stone-200">
                          {u.email || <span className="text-stone-500">(이메일 없음)</span>}
                          {u.email === 'casareborgia@gmail.com' && (
                            <span className="ml-2 px-1.5 py-0.5 text-[10px] rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">
                              OPERATOR
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-stone-300">{u.nickname || '-'}</td>
                        <td className="px-4 py-3 font-bold text-amber-400">
                          {u.credit_balance.toLocaleString()} C
                        </td>
                        <td className="px-4 py-3 text-stone-300">{u.session_count} 회</td>
                        <td className="px-4 py-3 text-stone-400">
                          {u.created_at ? new Date(u.created_at).toLocaleString('ko-KR') : '-'}
                        </td>
                        <td className="px-4 py-3 text-right">
                          <button
                            onClick={() => {
                              setSelectedUser({ id: u.id, email: u.email, credit: u.credit_balance });
                              setGrantAmount(100);
                              setGrantReason('운영자 보너스 지급');
                            }}
                            className="px-2.5 py-1 rounded-lg bg-stone-800 hover:bg-stone-700 text-stone-200 text-xs transition border border-stone-700"
                          >
                            크레딧 조정
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {/* 3단 - 최근 활동 로그 (상담 세션 / 크레딧 원장 탭) */}
        {data && (
          <section className="space-y-4">
            <div className="flex items-center justify-between border-b border-stone-800 pb-2">
              <div className="flex space-x-4">
                <button
                  onClick={() => setActiveTab('sessions')}
                  className={`pb-2 text-sm font-semibold transition border-b-2 ${
                    activeTab === 'sessions'
                      ? 'border-amber-400 text-amber-300'
                      : 'border-transparent text-stone-400 hover:text-stone-200'
                  }`}
                >
                  최근 상담 세션 로그 ({data.recent_sessions.length}건)
                </button>
                <button
                  onClick={() => setActiveTab('ledger')}
                  className={`pb-2 text-sm font-semibold transition border-b-2 ${
                    activeTab === 'ledger'
                      ? 'border-amber-400 text-amber-300'
                      : 'border-transparent text-stone-400 hover:text-stone-200'
                  }`}
                >
                  최근 크레딧 원장 입출금 내역 ({data.recent_ledger.length}건)
                </button>
              </div>
            </div>

            {/* 탭 1: 최근 상담 세션 */}
            {activeTab === 'sessions' && (
              <div className="overflow-x-auto rounded-2xl border border-stone-800 bg-stone-900/40">
                <table className="w-full text-left text-sm text-stone-300">
                  <thead className="bg-stone-900/80 text-xs uppercase text-stone-400 border-b border-stone-800">
                    <tr>
                      <th className="px-4 py-3">세션 일시</th>
                      <th className="px-4 py-3">사용자</th>
                      <th className="px-4 py-3">상담 질문 요약</th>
                      <th className="px-4 py-3">분류</th>
                      <th className="px-4 py-3">진행 턴</th>
                      <th className="px-4 py-3">저널 여부</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-stone-800/60 font-mono text-xs">
                    {data.recent_sessions.map((s) => (
                      <tr key={s.id} className="hover:bg-stone-800/30 transition">
                        <td className="px-4 py-3 text-stone-400 whitespace-nowrap">
                          {s.created_at ? new Date(s.created_at).toLocaleString('ko-KR') : '-'}
                        </td>
                        <td className="px-4 py-3 text-stone-200 whitespace-nowrap">
                          {s.user_email || <span className="text-stone-500">익명</span>}
                        </td>
                        <td className="px-4 py-3 text-stone-300 max-w-xs truncate font-sans" title={s.raw_question}>
                          {s.raw_question}
                        </td>
                        <td className="px-4 py-3 text-stone-400">{s.topic_category || '일반'}</td>
                        <td className="px-4 py-3 text-amber-400">{s.turn_count} 턴</td>
                        <td className="px-4 py-3">
                          {s.has_journal ? (
                            <span className="px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-300 text-[10px]">저널생성</span>
                          ) : (
                            <span className="text-stone-500">-</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* 탭 2: 최근 크레딧 원장 내역 */}
            {activeTab === 'ledger' && (
              <div className="overflow-x-auto rounded-2xl border border-stone-800 bg-stone-900/40">
                <table className="w-full text-left text-sm text-stone-300">
                  <thead className="bg-stone-900/80 text-xs uppercase text-stone-400 border-b border-stone-800">
                    <tr>
                      <th className="px-4 py-3">거래 일시</th>
                      <th className="px-4 py-3">사용자</th>
                      <th className="px-4 py-3">변동 수량</th>
                      <th className="px-4 py-3">이벤트 유형</th>
                      <th className="px-4 py-3">거래 사유</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-stone-800/60 font-mono text-xs">
                    {data.recent_ledger.map((l) => (
                      <tr key={l.id} className="hover:bg-stone-800/30 transition">
                        <td className="px-4 py-3 text-stone-400 whitespace-nowrap">
                          {l.created_at ? new Date(l.created_at).toLocaleString('ko-KR') : '-'}
                        </td>
                        <td className="px-4 py-3 text-stone-200 whitespace-nowrap">
                          {l.user_email || <span className="text-stone-500">익명</span>}
                        </td>
                        <td className={`px-4 py-3 font-bold ${l.amount > 0 ? 'text-emerald-400' : 'text-amber-500'}`}>
                          {l.amount > 0 ? `+${l.amount}` : l.amount} C
                        </td>
                        <td className="px-4 py-3 text-stone-300">
                          <span className="px-1.5 py-0.5 rounded bg-stone-800 text-stone-300 text-[10px]">
                            {l.event_type || 'TRANSACTION'}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-stone-400 font-sans">{l.reason || '-'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        )}
      </main>

      {/* 크레딧 지급/조정 모달 */}
      {selectedUser && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-2xl bg-stone-900 border border-stone-800 p-6 space-y-5 shadow-2xl animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between border-b border-stone-800 pb-3">
              <h3 className="text-base font-bold text-stone-100 flex items-center space-x-2">
                <span>💰 크레딧 수동 지급 / 조정</span>
              </h3>
              <button
                onClick={() => setSelectedUser(null)}
                className="text-stone-400 hover:text-stone-200 text-lg leading-none"
              >
                ✕
              </button>
            </div>

            {grantSuccessMsg ? (
              <div className="p-4 rounded-xl bg-emerald-950/60 border border-emerald-800 text-emerald-300 text-sm font-medium text-center">
                {grantSuccessMsg}
              </div>
            ) : (
              <form onSubmit={handleGrantCredit} className="space-y-4">
                <div className="p-3 rounded-xl bg-stone-950 border border-stone-800 text-xs space-y-1">
                  <div className="text-stone-400">대상 회원:</div>
                  <div className="text-stone-200 font-mono font-medium">{selectedUser.email || selectedUser.id}</div>
                  <div className="text-stone-400 pt-1">
                    현재 잔액: <span className="text-amber-400 font-bold">{selectedUser.credit.toLocaleString()} C</span>
                  </div>
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs text-stone-400 font-medium">지급할 크레딧 수량</label>
                  <input
                    type="number"
                    min={1}
                    max={100000}
                    value={grantAmount}
                    onChange={(e) => setGrantAmount(parseInt(e.target.value, 10) || 0)}
                    className="w-full px-3 py-2 rounded-xl bg-stone-950 border border-stone-800 text-stone-100 font-mono text-base focus:outline-none focus:border-amber-500"
                    required
                  />
                  {/* 프리셋 버튼 */}
                  <div className="flex space-x-2 pt-1">
                    {[50, 100, 500, 1000].map((preset) => (
                      <button
                        key={preset}
                        type="button"
                        onClick={() => setGrantAmount(preset)}
                        className="px-2.5 py-1 text-xs rounded-lg bg-stone-800 hover:bg-stone-700 text-stone-300 transition"
                      >
                        +{preset}C
                      </button>
                    ))}
                  </div>
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs text-stone-400 font-medium">지급 사유</label>
                  <input
                    type="text"
                    value={grantReason}
                    onChange={(e) => setGrantReason(e.target.value)}
                    placeholder="예: 운영자 보너스 지급, 테스트 지원 등"
                    className="w-full px-3 py-2 rounded-xl bg-stone-950 border border-stone-800 text-stone-100 text-sm focus:outline-none focus:border-amber-500"
                    required
                  />
                </div>

                <div className="flex space-x-3 pt-3">
                  <button
                    type="button"
                    onClick={() => setSelectedUser(null)}
                    className="flex-1 py-2.5 rounded-xl bg-stone-800 hover:bg-stone-700 text-stone-300 text-sm font-medium transition"
                  >
                    취소
                  </button>
                  <button
                    type="submit"
                    disabled={isSubmittingGrant || grantAmount <= 0}
                    className="flex-1 py-2.5 rounded-xl bg-amber-500 hover:bg-amber-600 text-stone-950 text-sm font-bold transition disabled:opacity-50"
                  >
                    {isSubmittingGrant ? '처리 중...' : '크레딧 지급 확정'}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
