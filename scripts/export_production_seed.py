import asyncio
import json
from sqlalchemy import text
from core.db import AsyncSessionLocal

async def export_sql():
    output_file = "scripts/supabase_production_seed.sql"
    print(f"Generating {output_file}...")

    sql_statements = []

    # 1. Extensions
    sql_statements.append("-- 1. Enable Extensions")
    sql_statements.append("CREATE EXTENSION IF NOT EXISTS vector;")
    sql_statements.append("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";")
    sql_statements.append("")

    # 2. Base Tables DDL
    sql_statements.append("""
-- 2. Core Tables
CREATE TABLE IF NOT EXISTS public.hexagrams (
    id INT PRIMARY KEY,
    binary_code VARCHAR(6) UNIQUE,
    symbol VARCHAR(10),
    name_ko VARCHAR(50),
    name_hanja VARCHAR(50) NOT NULL,
    name_full VARCHAR(100),
    judgment_text TEXT NOT NULL,
    judgment_ko TEXT,
    tanjon_text TEXT,
    xiang_text TEXT,
    wenyan_text TEXT
);

CREATE TABLE IF NOT EXISTS public.lines (
    id SERIAL PRIMARY KEY,
    hexagram_id INT NOT NULL REFERENCES public.hexagrams(id) ON DELETE CASCADE,
    line_number INT NOT NULL,
    statement_text TEXT NOT NULL,
    statement_ko TEXT,
    small_xiang_text TEXT,
    CONSTRAINT uq_line_hexagram_linenumber UNIQUE (hexagram_id, line_number)
);

CREATE TABLE IF NOT EXISTS public.interpretation_chunks (
    id SERIAL PRIMARY KEY,
    hexagram_id INT REFERENCES public.hexagrams(id) ON DELETE SET NULL,
    line_number INT,
    category VARCHAR(50) NOT NULL,
    source_type VARCHAR(30),
    content TEXT NOT NULL,
    content_ko TEXT,
    embedding vector(768)
);

CREATE INDEX IF NOT EXISTS ix_interpretation_chunks_embedding_hnsw 
ON public.interpretation_chunks USING hnsw (embedding vector_cosine_ops) 
WITH (m = 16, ef_construction = 64);

CREATE TABLE IF NOT EXISTS public.counsel_sessions (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(50),
    raw_question TEXT NOT NULL,
    clarified_question TEXT,
    topic_category VARCHAR(50),
    is_duplicate BOOLEAN DEFAULT FALSE NOT NULL,
    duplicate_session_ref VARCHAR(36) REFERENCES public.counsel_sessions(id) ON DELETE SET NULL,
    status VARCHAR(20) DEFAULT 'active' NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

CREATE TABLE IF NOT EXISTS public.counsel_turns (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(36) NOT NULL REFERENCES public.counsel_sessions(id) ON DELETE CASCADE,
    turn_number INT NOT NULL,
    original_hexagram_id INT REFERENCES public.hexagrams(id),
    transformed_hexagram_id INT REFERENCES public.hexagrams(id),
    changing_lines JSONB,
    user_message TEXT NOT NULL,
    agent_response TEXT NOT NULL,
    contextual_mapping TEXT,
    evidence_items JSONB,
    needs_followup BOOLEAN DEFAULT TRUE NOT NULL,
    is_final BOOLEAN DEFAULT FALSE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    CONSTRAINT uq_turn_session_turnnumber UNIQUE (session_id, turn_number)
);

CREATE TABLE IF NOT EXISTS public.journal_entries (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(36) UNIQUE NOT NULL REFERENCES public.counsel_sessions(id) ON DELETE CASCADE,
    summary TEXT NOT NULL,
    key_insights TEXT NOT NULL,
    action_items TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Profiles, credit tables, RLS, grants, and auth-trigger functions are not
-- seed data.  Alembic is their only owner; see revisions c3a91f4d6b27 and
-- e8b72c4a91d0.  Re-emitting those objects here could reopen a deprecated
-- SECURITY DEFINER RPC or overwrite hardened privileges.
""")

    async with AsyncSessionLocal() as session:
        # 3. Hexagrams Data
        print("Exporting 64 Hexagrams...")
        hex_rows = (await session.execute(text("SELECT * FROM hexagrams ORDER BY id"))).mappings().all()
        for r in hex_rows:
            q_text = r['judgment_text'].replace("'", "''")
            q_ko = r['judgment_ko'].replace("'", "''") if r['judgment_ko'] else None
            tanjon = r['tanjon_text'].replace("'", "''") if r['tanjon_text'] else None
            xiang = r['xiang_text'].replace("'", "''") if r['xiang_text'] else None
            wenyan = r['wenyan_text'].replace("'", "''") if r['wenyan_text'] else None
            
            sql_statements.append(
                f"INSERT INTO public.hexagrams (id, binary_code, symbol, name_ko, name_hanja, name_full, judgment_text, judgment_ko, tanjon_text, xiang_text, wenyan_text) "
                f"VALUES ({r['id']}, '{r['binary_code']}', '{r['symbol']}', '{r['name_ko']}', '{r['name_hanja']}', '{r['name_full']}', '{q_text}', "
                f"{repr(q_ko) if q_ko else 'NULL'}, {repr(tanjon) if tanjon else 'NULL'}, {repr(xiang) if xiang else 'NULL'}, {repr(wenyan) if wenyan else 'NULL'}) "
                f"ON CONFLICT (id) DO NOTHING;"
            )

        # 4. Lines Data
        print("Exporting 386 Lines...")
        line_rows = (await session.execute(text("SELECT * FROM lines ORDER BY id"))).mappings().all()
        for r in line_rows:
            st_text = r['statement_text'].replace("'", "''")
            st_ko = r['statement_ko'].replace("'", "''") if r['statement_ko'] else None
            s_xiang = r['small_xiang_text'].replace("'", "''") if r['small_xiang_text'] else None
            
            sql_statements.append(
                f"INSERT INTO public.lines (id, hexagram_id, line_number, statement_text, statement_ko, small_xiang_text) "
                f"VALUES ({r['id']}, {r['hexagram_id']}, {r['line_number']}, '{st_text}', {repr(st_ko) if st_ko else 'NULL'}, {repr(s_xiang) if s_xiang else 'NULL'}) "
                f"ON CONFLICT (id) DO NOTHING;"
            )

        # 5. Interpretation Chunks Data (2,536 chunks)
        print("Exporting 2,536 Interpretation Chunks...")
        chunk_rows = (await session.execute(text("SELECT id, hexagram_id, line_number, category, source_type, content, content_ko, embedding::text as emb FROM interpretation_chunks ORDER BY id"))).mappings().all()
        for r in chunk_rows:
            content = r['content'].replace("'", "''")
            content_ko = r['content_ko'].replace("'", "''") if r['content_ko'] else None
            hex_id = r['hexagram_id'] if r['hexagram_id'] is not None else 'NULL'
            line_num = r['line_number'] if r['line_number'] is not None else 'NULL'
            emb = f"'{r['emb']}'::vector" if r['emb'] else 'NULL'
            
            sql_statements.append(
                f"INSERT INTO public.interpretation_chunks (id, hexagram_id, line_number, category, source_type, content, content_ko, embedding) "
                f"VALUES ({r['id']}, {hex_id}, {line_num}, '{r['category']}', '{r['source_type']}', '{content}', {repr(content_ko) if content_ko else 'NULL'}, {emb}) "
                f"ON CONFLICT (id) DO NOTHING;"
            )

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(sql_statements))

    print(f"✅ Export completed: {output_file}")

if __name__ == "__main__":
    asyncio.run(export_sql())
