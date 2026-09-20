'use client';

import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { User, Session } from '@supabase/supabase-js';
import { supabase } from '@/lib/supabaseClient';
import { fetchMyCredits } from '@/lib/creditOperation';
import { getConsentApi, postConsentApi, withdrawConsentApi } from '@/lib/api';
import { fetchPublicConfig } from '@/lib/publicConfig';
import { evaluateConsentStatus, ConsentEvaluationResult } from '@/lib/consentStatus';

export interface Profile {
  id: string;
  email: string | null;
  nickname?: string | null;
  credit: number | null; // unknown / null 상태 수용 (절대 50으로 임의 추정 금지)
  welcome_granted?: boolean;
  avatar_url: string | null;
}

interface AuthContextType {
  user: User | null;
  session: Session | null;
  profile: Profile | null;
  isLoading: boolean;
  consentError: string | null;
  isConsentRecorded: boolean;
  recordConsent: () => Promise<boolean>;
  withdrawConsent: () => Promise<boolean>;
  checkConsent: () => Promise<ConsentEvaluationResult>;
  signInWithGoogle: () => Promise<void>;
  signOut: () => Promise<void>;
  refreshProfile: () => Promise<void>;
  updateCredit: (newBalance: number | null) => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [consentError, setConsentError] = useState<string | null>(null);
  const [isConsentRecorded, setIsConsentRecorded] = useState<boolean>(false);

  /**
   * 서버 단일 출처(GET /api/me/consent) 및 publicConfig로부터 동의 유효성을 실시간 판정합니다.
   * 추측이나 로컬 기본값(false)에 머물지 않고 서버의 실제 동의 이력과 개정 여부를 대조합니다.
   */
  const checkConsent = useCallback(async (): Promise<ConsentEvaluationResult> => {
    try {
      setConsentError(null);
      const publicConfig = await fetchPublicConfig();
      const expectedVersion = (publicConfig.legal_documents_version || '').trim();
      if (!expectedVersion) {
        const errorDetails = '서비스 정책 문서 버전이 설정되지 않아 준비 중입니다.';
        setConsentError(errorDetails);
        setIsConsentRecorded(false);
        return {
          status: 'NEEDS_CONSENT',
          needsReconsent: true,
          reason: 'VERSION_MISMATCH',
          details: errorDetails,
        };
      }
      const consentRes = await getConsentApi();
      const evalResult = evaluateConsentStatus(consentRes.current, expectedVersion);
      if (evalResult.status === 'VALID') {
        setIsConsentRecorded(true);
      } else {
        setIsConsentRecorded(false);
        if (evalResult.details) {
          setConsentError(evalResult.details);
        }
      }
      return evalResult;
    } catch (err: unknown) {
      console.error('동의 상태 확인 실패:', err);
      setIsConsentRecorded(false);
      const errorMsg = err instanceof Error ? err.message : '동의 상태를 확인할 수 없습니다.';
      setConsentError(errorMsg);
      return {
        status: 'NEEDS_CONSENT',
        needsReconsent: true,
        reason: 'NO_RECORD',
        details: errorMsg,
      };
    }
  }, []);

  /**
   * 법적 동의 및 연령 확인 기록 (AG-1 / A19, A21, A22, A24, FIX-4)
   * 사용자의 명시적 동의 액션(체크 후 확인 클릭) 시에만 호출됩니다.
   * 자동 호출 경로는 제거되었습니다.
   */
  const recordConsent = async (): Promise<boolean> => {
    try {
      setConsentError(null);
      const publicConfig = await fetchPublicConfig();
      const version = (publicConfig.legal_documents_version || '').trim();
      if (!version) {
        setConsentError('서비스 정책 문서 버전이 설정되지 않아 준비 중입니다.');
        setIsConsentRecorded(false);
        return false;
      }
      await postConsentApi(version, version, true);
      setIsConsentRecorded(true);
      return true;
    } catch (err: unknown) {
      console.error('동의 기록 영속화 실패:', err);
      const message = err instanceof Error ? err.message : '법적 동의 기록 저장에 실패했습니다. 다시 시도해 주세요.';
      setConsentError(message);
      setIsConsentRecorded(false);
      return false;
    }
  };

  /**
   * 법적 동의 철회 (A23)
   * 철회 성공 시 isConsentRecorded를 false로 전환하여 상담 생성을 즉시 차단합니다.
   */
  const withdrawConsent = async (): Promise<boolean> => {
    try {
      setConsentError(null);
      await withdrawConsentApi();
      setIsConsentRecorded(false);
      return true;
    } catch (err: unknown) {
      console.error('동의 철회 실패:', err);
      const message = err instanceof Error ? err.message : '동의 철회 처리에 실패했습니다. 다시 시도해 주세요.';
      setConsentError(message);
      return false;
    }
  };

  /**
   * 서버 단일 출처(GET /api/me/credits)로부터 인증된 사용자 잔액을 안전하게 조회합니다.
   * Supabase profiles 테이블을 직조회하지 않으며, API 실패 시 50으로 추정하지 않고 null(unknown)로 유지합니다.
   * 자동 동의 기록(recordConsent)을 호출하지 않고, 실제 서버 동의 상태(checkConsent)만 조회합니다.
   */
  const fetchProfile = async (currentUser: User, currentSession?: Session | null) => {
    const token = currentSession?.access_token || session?.access_token;
    let serverCredits: number | null = null;
    let welcomeGranted = false;

    if (token) {
      const creditsData = await fetchMyCredits(token);
      if (creditsData) {
        serverCredits = creditsData.remaining_credits;
        welcomeGranted = creditsData.welcome_granted;
      }
      // 자동 동의 기록 제거: 실제 동의 상태만 서버에서 조회하여 판정
      await checkConsent();
    }

    setProfile({
      id: currentUser.id,
      email: currentUser.email || null,
      nickname: currentUser.user_metadata?.name || currentUser.user_metadata?.full_name || null,
      credit: serverCredits, // 실패 시 null 유지
      welcome_granted: welcomeGranted,
      avatar_url: currentUser.user_metadata?.avatar_url || null,
    });
  };

  useEffect(() => {
    // 1. 현재 세션 확인
    supabase.auth.getSession().then(({ data: { session: currentSession } }) => {
      setSession(currentSession);
      setUser(currentSession?.user ?? null);
      if (currentSession?.user) {
        fetchProfile(currentSession.user, currentSession);
      }
      setIsLoading(false);
    });

    // 2. Auth 상태 변화 리스너
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      async (_event, currentSession) => {
        setSession(currentSession);
        setUser(currentSession?.user ?? null);
        if (currentSession?.user) {
          await fetchProfile(currentSession.user, currentSession);
        } else {
          setProfile(null);
        }
        setIsLoading(false);
      }
    );

    return () => {
      subscription.unsubscribe();
    };
  }, []);

  const signInWithGoogle = async () => {
    const siteUrl = typeof window !== 'undefined' ? window.location.origin : 'http://localhost:3000';
    await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: {
        redirectTo: `${siteUrl}/auth/callback`,
        queryParams: {
          access_type: 'offline',
          prompt: 'consent',
        },
      },
    });
  };

  const signOut = async () => {
    await supabase.auth.signOut();
    setUser(null);
    setSession(null);
    setProfile(null);
    setIsConsentRecorded(false);
    setConsentError(null);
  };

  const refreshProfile = async () => {
    if (user) {
      await fetchProfile(user, session);
    }
  };

  const updateCredit = (newBalance: number | null) => {
    setProfile((prev) => {
      if (prev) {
        return { ...prev, credit: newBalance };
      }
      return {
        id: user?.id || '',
        email: user?.email || null,
        credit: newBalance,
        welcome_granted: false,
        avatar_url: null,
      };
    });
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        session,
        profile,
        isLoading,
        consentError,
        isConsentRecorded,
        recordConsent,
        withdrawConsent,
        checkConsent,
        signInWithGoogle,
        signOut,
        refreshProfile,
        updateCredit,
      }}
    >
      {children}
    </AuthContext.Provider>
  );

}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
