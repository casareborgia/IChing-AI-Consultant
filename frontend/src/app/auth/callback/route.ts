import { NextResponse } from 'next/server';
import { createServerClient } from '@supabase/ssr';
import { cookies } from 'next/headers';

const FALLBACK_SUPABASE_URL = 'https://ovkrhkfhscsyxixsxenk.supabase.co';
const FALLBACK_SUPABASE_ANON_KEY =
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im92a3Joa2Zoc2NzeXhpeHN4ZW5rIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODA0NTExMTcsImV4cCI6MjA5NjAyNzExN30.Y9JTdS13njPN7FRm1owfSJxtqt4ShiCDVwbMqP9yJ10';

export async function GET(request: Request) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get('code');
  const next = searchParams.get('next') ?? '/';

  if (code) {
    try {
      const cookieStore = await cookies();
      const supabase = createServerClient(
        process.env.NEXT_PUBLIC_SUPABASE_URL || FALLBACK_SUPABASE_URL,
        process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || FALLBACK_SUPABASE_ANON_KEY,
        {
          cookies: {
            getAll() {
              return cookieStore.getAll();
            },
            setAll(cookiesToSet) {
              try {
                cookiesToSet.forEach(({ name, value, options }) =>
                  cookieStore.set(name, value, options)
                );
              } catch {
                // The `setAll` method was called from a Server Component.
              }
            },
          },
        }
      );

      const { error } = await supabase.auth.exchangeCodeForSession(code);
      if (!error) {
        return NextResponse.redirect(`${origin}${next}`);
      }
      console.error('exchangeCodeForSession error:', error);
    } catch (err) {
      console.error('Auth callback exception:', err);
    }
  }

  // 오류 발생 시 홈으로 안전하게 리다이렉트
  return NextResponse.redirect(`${origin}/?error=auth_failed`);
}

