'use client';

import React, { useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { supabase } from '@/lib/supabaseClient';

function AuthCallbackContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  useEffect(() => {
    let isMounted = true;

    const processAuth = async () => {
      try {
        const code = searchParams.get('code');
        const next = searchParams.get('next') || '/';

        if (code) {
          // 브라우저 클라이언트에서 직접 PKCE 세션 교환 수행
          const { error } = await supabase.auth.exchangeCodeForSession(code);
          if (error) {
            console.error('Session exchange error:', error);
          }
        }

        // 세션 상태 확인 후 홈/대상 경로로 부드럽게 이동
        const { data: { session } } = await supabase.auth.getSession();
        if (isMounted) {
          if (session) {
            router.replace(next);
          } else {
            router.replace('/');
          }
        }
      } catch (err) {
        console.error('Auth callback failed:', err);
        if (isMounted) {
          router.replace('/?error=auth_failed');
        }
      }
    };

    processAuth();

    return () => {
      isMounted = false;
    };
  }, [router, searchParams]);

  return (
    <div className="min-h-screen bg-stone-950 flex flex-col items-center justify-center p-4 text-stone-200">
      <div className="relative flex items-center justify-center">
        {/* Glow effect */}
        <div className="absolute h-24 w-24 rounded-full bg-amber-500/20 blur-xl animate-pulse" />
        {/* Zen Spinner */}
        <div className="h-12 w-12 rounded-full border-2 border-amber-500/20 border-t-amber-400 animate-spin" />
        <span className="absolute font-serif text-amber-300 text-sm">䷀</span>
      </div>
      <p className="mt-6 font-serif text-sm text-stone-400 tracking-wide">
        성찰 세션을 안전하게 연결하는 중입니다...
      </p>
    </div>
  );
}

export default function AuthCallbackPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-stone-950 flex items-center justify-center p-4 text-stone-400">
          <p className="font-serif text-sm">인증 상태 확인 중...</p>
        </div>
      }
    >
      <AuthCallbackContent />
    </Suspense>
  );
}
