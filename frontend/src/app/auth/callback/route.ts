import { NextResponse, type NextRequest } from 'next/server';
import { createServerClient } from '@supabase/ssr';

const FALLBACK_SUPABASE_URL = 'https://ovkrhkfhscsyxixsxenk.supabase.co';
const FALLBACK_SUPABASE_ANON_KEY =
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im92a3Joa2Zoc2NzeXhpeHN4ZW5rIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODA0NTExMTcsImV4cCI6MjA5NjAyNzExN30.Y9JTdS13njPN7FRm1owfSJxtqt4ShiCDVwbMqP9yJ10';

export async function GET(request: NextRequest) {
  const requestUrl = new URL(request.url);
  const code = requestUrl.searchParams.get('code');
  const next = requestUrl.searchParams.get('next') ?? '/';

  // Vercel 프록시 헤더 및 환경변수 기반 안정적인 Base URL 결정
  const forwardedHost = request.headers.get('x-forwarded-host');
  const forwardedProto = request.headers.get('x-forwarded-proto') || 'https';
  const baseUrl = forwardedHost
    ? `${forwardedProto}://${forwardedHost}`
    : process.env.NEXT_PUBLIC_SITE_URL || requestUrl.origin;

  if (code) {
    try {
      const response = NextResponse.redirect(`${baseUrl}${next}`);

      const supabase = createServerClient(
        process.env.NEXT_PUBLIC_SUPABASE_URL || FALLBACK_SUPABASE_URL,
        process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || FALLBACK_SUPABASE_ANON_KEY,
        {
          cookies: {
            getAll() {
              return request.cookies.getAll();
            },
            setAll(cookiesToSet) {
              cookiesToSet.forEach(({ name, value, options }) =>
                response.cookies.set(name, value, options)
              );
            },
          },
        }
      );

      const { error } = await supabase.auth.exchangeCodeForSession(code);
      if (!error) {
        return response;
      }
      console.error('exchangeCodeForSession error:', error);
    } catch (err) {
      console.error('Auth callback exception:', err);
    }
  }

  // 오류 발생 시 홈으로 안전하게 리다이렉트
  return NextResponse.redirect(`${baseUrl}/?error=auth_failed`);
}


