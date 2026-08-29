import { createBrowserClient } from '@supabase/ssr';

// 하드코딩 폴백을 두지 않는다.
//
// 공개 키라 유출 위험은 없지만, 값이 코드에 박혀 있으면 환경변수가 빠진 것을
// 아무도 모른다 — 실제로 NEXT_PUBLIC_* 세 개가 Vercel 에 없는 채로 배포돼
// 있었고, 폴백 덕에 로그인만 되고 상담은 localhost 를 부르고 있었다.
// 값이 없으면 조용히 넘어가는 대신 즉시 터지게 한다.
//
// 로컬 개발에는 frontend/.env.local 이 필요하다 (.env.example 참고).
const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

if (!supabaseUrl || !supabaseAnonKey) {
  throw new Error(
    'NEXT_PUBLIC_SUPABASE_URL / NEXT_PUBLIC_SUPABASE_ANON_KEY 가 설정되지 않았습니다. ' +
      'Vercel 환경변수 또는 frontend/.env.local 을 확인하세요.'
  );
}

export const supabase = createBrowserClient(supabaseUrl, supabaseAnonKey);
