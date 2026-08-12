-- 컨테이너 최초 기동 시 1회 실행된다.
-- pgvector 확장을 켜야 vector 타입과 유사도 검색 연산자를 쓸 수 있다.
CREATE EXTENSION IF NOT EXISTS vector;

-- UUID 기본키를 쓸 경우 필요 (gen_random_uuid)
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 한글 부분일치 검색(LIKE '%키워드%')을 인덱스로 가속하려면 필요
CREATE EXTENSION IF NOT EXISTS pg_trgm;
