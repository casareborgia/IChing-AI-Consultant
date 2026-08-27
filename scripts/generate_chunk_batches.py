import asyncio
import os
from sqlalchemy import text
from core.db import AsyncSessionLocal

async def create_batch_files():
    os.makedirs("scripts/supabase_batches", exist_ok=True)
    
    async with AsyncSessionLocal() as session:
        # 1. 64 Hexagrams
        hex_rows = (await session.execute(text("SELECT * FROM hexagrams ORDER BY id"))).mappings().all()
        hex_values = []
        for r in hex_rows:
            q_text = r['judgment_text'].replace("'", "''")
            q_ko = r['judgment_ko'].replace("'", "''") if r['judgment_ko'] else None
            tanjon = r['tanjon_text'].replace("'", "''") if r['tanjon_text'] else None
            xiang = r['xiang_text'].replace("'", "''") if r['xiang_text'] else None
            wenyan = r['wenyan_text'].replace("'", "''") if r['wenyan_text'] else None
            v = f"({r['id']}, '{r['binary_code']}', '{r['symbol']}', '{r['name_ko']}', '{r['name_hanja']}', '{r['name_full']}', '{q_text}', {repr(q_ko) if q_ko else 'NULL'}, {repr(tanjon) if tanjon else 'NULL'}, {repr(xiang) if xiang else 'NULL'}, {repr(wenyan) if wenyan else 'NULL'})"
            hex_values.append(v)
        
        with open("scripts/supabase_batches/01_hexagrams.sql", "w", encoding="utf-8") as f:
            f.write(f"INSERT INTO public.hexagrams (id, binary_code, symbol, name_ko, name_hanja, name_full, judgment_text, judgment_ko, tanjon_text, xiang_text, wenyan_text) VALUES {','.join(hex_values)} ON CONFLICT (id) DO NOTHING;")

        # 2. 386 Lines
        line_rows = (await session.execute(text("SELECT * FROM lines ORDER BY id"))).mappings().all()
        line_values = []
        for r in line_rows:
            st_text = r['statement_text'].replace("'", "''")
            st_ko = r['statement_ko'].replace("'", "''") if r['statement_ko'] else None
            s_xiang = r['small_xiang_text'].replace("'", "''") if r['small_xiang_text'] else None
            v = f"({r['id']}, {r['hexagram_id']}, {r['line_number']}, '{st_text}', {repr(st_ko) if st_ko else 'NULL'}, {repr(s_xiang) if s_xiang else 'NULL'})"
            line_values.append(v)
            
        with open("scripts/supabase_batches/02_lines.sql", "w", encoding="utf-8") as f:
            f.write(f"INSERT INTO public.lines (id, hexagram_id, line_number, statement_text, statement_ko, small_xiang_text) VALUES {','.join(line_values)} ON CONFLICT (id) DO NOTHING;")

        # 3. 2,536 Chunks (100개씩 분할)
        chunk_rows = (await session.execute(text("SELECT id, hexagram_id, line_number, category, source_type, content, content_ko, embedding::text as emb FROM interpretation_chunks ORDER BY id"))).mappings().all()
        
        batch_size = 100
        total_batches = (len(chunk_rows) + batch_size - 1) // batch_size
        
        for b_idx in range(total_batches):
            batch_slice = chunk_rows[b_idx * batch_size : (b_idx + 1) * batch_size]
            chunk_values = []
            for r in batch_slice:
                content = r['content'].replace("'", "''")
                content_ko = r['content_ko'].replace("'", "''") if r['content_ko'] else None
                hex_id = r['hexagram_id'] if r['hexagram_id'] is not None else 'NULL'
                line_num = r['line_number'] if r['line_number'] is not None else 'NULL'
                emb = f"'{r['emb']}'::vector" if r['emb'] else 'NULL'
                v = f"({r['id']}, {hex_id}, {line_num}, '{r['category']}', '{r['source_type']}', '{content}', {repr(content_ko) if content_ko else 'NULL'}, {emb})"
                chunk_values.append(v)
            
            sql = f"INSERT INTO public.interpretation_chunks (id, hexagram_id, line_number, category, source_type, content, content_ko, embedding) VALUES {','.join(chunk_values)} ON CONFLICT (id) DO NOTHING;"
            file_name = f"scripts/supabase_batches/03_chunks_{b_idx+1:02d}_of_{total_batches:02d}.sql"
            with open(file_name, "w", encoding="utf-8") as f:
                f.write(sql)

        print(f"Generated {total_batches} chunk batch files in scripts/supabase_batches/")

if __name__ == "__main__":
    asyncio.run(create_batch_files())
