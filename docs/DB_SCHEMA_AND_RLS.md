# Supabase DB 스키마 & RLS 설계

`docs/DEPLOYMENT_AND_MONETIZATION_BLUEPRINT.md`에서 분리해 온 문서다. 원 문서에는
가격·원가 등 대외 공개 대상이 아닌 내용이 함께 있어 리포지토리에서 제외했고,
스키마는 운영 문서들이 참조하므로 여기 남긴다.

`profiles`·`credit_ledger`는 Supabase Auth의 `auth.users`에 붙는 애플리케이션 테이블이다.
괘·효·RAG 청크 등 상담 도메인 스키마는 Alembic(`migrations/`)이 관리한다 — 이 파일이 아니다.


```sql
-- 1. 사용자 프로필 및 크레딧 테이블
CREATE TABLE IF NOT EXISTS public.profiles (
  id UUID REFERENCES auth.users ON DELETE CASCADE PRIMARY KEY,
  email TEXT,
  nickname TEXT,
  avatar_url TEXT,
  credit_balance INT DEFAULT 50 CHECK (credit_balance >= 0),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

CREATE POLICY "자신의 프로필만 조회 가능" 
ON public.profiles FOR SELECT 
USING (auth.uid() = id);

-- 2. 크레딧 증감 이력 (Audit Log)
CREATE TABLE IF NOT EXISTS public.credit_ledger (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE,
  amount INT NOT NULL,
  reason TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

ALTER TABLE public.credit_ledger ENABLE ROW LEVEL SECURITY;

CREATE POLICY "자신의 크레딧 내역만 조회 가능" 
ON public.credit_ledger FOR SELECT 
USING (auth.uid() = user_id);

-- 3. 신규 가입 시 50 웰컴 크레딧 자동 생성 트리거
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO public.profiles (id, email, nickname, avatar_url, credit_balance)
  VALUES (
    NEW.id,
    NEW.email,
    COALESCE(NEW.raw_user_meta_data->>'full_name', NEW.raw_user_meta_data->>'name', '내담자'),
    NEW.raw_user_meta_data->>'avatar_url',
    50
  );
  
  INSERT INTO public.credit_ledger (user_id, amount, reason)
  VALUES (NEW.id, 50, '신규 가입 웰컴 크레딧');
  
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE OR REPLACE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- 4. 크레딧 차감 원자적 트랜잭션 함수 (RPC)
CREATE OR REPLACE FUNCTION public.deduct_credit(target_user_id UUID, deduct_amount INT)
RETURNS VOID AS $$
BEGIN
  UPDATE public.profiles
  SET credit_balance = credit_balance - deduct_amount,
      updated_at = NOW()
  WHERE id = target_user_id AND credit_balance >= deduct_amount;

  IF NOT FOUND THEN
    RAISE EXCEPTION '크레딧이 부족합니다.';
  END IF;

  INSERT INTO public.credit_ledger (user_id, amount, reason)
  VALUES (target_user_id, -deduct_amount, '주역 성찰 상담 세션 시작');
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
```

---

