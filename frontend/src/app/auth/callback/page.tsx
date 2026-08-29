'use client';

import React, { useEffect, useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { supabase } from '@/lib/supabaseClient';

// GoTrue/공급자가 되돌려주는 오류 코드 → 사용자에게 보일 문구
const OAUTH_ERROR_LABELS: Record<string, string> = {
  access_denied: '로그인이 취소되었습니다.',
  server_error: '인증 서버에서 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.',
  bad_oauth_state: '인증 상태가 만료되었습니다. 처음부터 다시 로그인해 주세요.',
};

// 외부 도메인으로 튕기지 않도록 상대경로만 허용한다
function safeNext(raw: string | null): string {
  if (!raw || !raw.startsWith('/') || raw.startsWith('//')) return '/';
  return raw;
}

function AuthCallbackContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [failure, setFailure] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const processAuth = async () => {
      // 1. 공급자/GoTrue가 오류를 되돌려준 경우를 먼저 가른다
      const errorCode = searchParams.get('error') || searchParams.get('error_code');
      if (errorCode) {
        const description = searchParams.get('error_description');
        setFailure(description || OAUTH_ERROR_LABELS[errorCode] || errorCode);
        return;
      }

      const code = searchParams.get('code');
      let exchangeError: string | null = null;

      if (code) {
        const { error } = await supabase.auth.exchangeCodeForSession(code);
        if (error) exchangeError = error.message;
      }

      // createBrowserClient는 detectSessionInUrl이 켜져 있어 위 교환보다 먼저
      // 코드를 소진하는 경우가 있다. 그때 위 호출은 실패하므로,
      // 성공 여부는 오류 객체가 아니라 세션 유무로 판정한다.
      const { data: { session } } = await supabase.auth.getSession();
      if (cancelled) return;

      if (session) {
        router.replace(safeNext(searchParams.get('next')));
        return;
      }

      setFailure(
        exchangeError ||
          (code
            ? '세션을 생성하지 못했습니다. 다시 로그인해 주세요.'
            : '인증 코드가 전달되지 않았습니다. 다시 로그인해 주세요.')
      );
    };

    processAuth().catch((err) => {
      if (cancelled) return;
      setFailure(err instanceof Error ? err.message : String(err));
    });

    return () => {
      cancelled = true;
    };
  }, [router, searchParams]);

  if (failure) {
    return (
      <div className="min-h-screen bg-stone-950 flex flex-col items-center justify-center p-4 text-stone-200">
        <div className="w-full max-w-sm rounded-3xl border border-stone-800/80 bg-stone-900/70 p-8 text-center">
          <div className="inline-flex h-14 w-14 items-center justify-center rounded-2xl border border-amber-500/30 bg-amber-500/10 font-serif text-2xl text-amber-300">
            ䷿
          </div>
          <h1 className="mt-4 font-serif text-lg text-stone-100">로그인을 마치지 못했습니다</h1>
          <p className="mt-3 break-words text-sm text-stone-400">{failure}</p>
          <button
            onClick={() => router.replace('/')}
            className="mt-6 w-full rounded-2xl border border-stone-700 bg-stone-800/80 px-5 py-3 text-sm font-semibold text-stone-100 transition hover:bg-stone-800"
          >
            처음으로 돌아가기
          </button>
        </div>
      </div>
    );
  }

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
