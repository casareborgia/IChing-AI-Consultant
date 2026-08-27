import asyncio
from sqlalchemy import text
from core.db import AsyncSessionLocal

async def extract_batches():
    async with AsyncSessionLocal() as session:
        # 1. Hexagrams SQL
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
        
        hex_sql = f"INSERT INTO public.hexagrams (id, binary_code, symbol, name_ko, name_hanja, name_full, judgment_text, judgment_ko, tanjon_text, xiang_text, wenyan_text) VALUES {','.join(hex_values)} ON CONFLICT (id) DO NOTHING;"

        # 2. Lines SQL
        line_rows = (await session.execute(text("SELECT * FROM lines ORDER BY id"))).mappings().all()
        line_values = []
        for r in line_rows:
            st_text = r['statement_text'].replace("'", "''")
            st_ko = r['statement_ko'].replace("'", "''") if r['statement_ko'] else None
            s_xiang = r['small_xiang_text'].replace("'", "''") if r['small_xiang_text'] else None
            v = f"({r['id']}, {r['hexagram_id']}, {r['line_number']}, '{st_text}', {repr(st_ko) if st_ko else 'NULL'}, {repr(s_xiang) if s_xiang else 'NULL'})"
            line_values.append(v)
            
        line_sql = f"INSERT INTO public.lines (id, hexagram_id, line_number, statement_text, statement_ko, small_xiang_text) VALUES {','.join(line_values)} ON CONFLICT (id) DO NOTHING;"

        with open("scripts/seed_hex_lines.sql", "w", encoding="utf-8") as f:
            f.write(hex_sql + "\n\n" + line_sql)
            
        print("Generated scripts/seed_hex_lines.sql")

if __name__ == "__main__":
    asyncio.run(extract_batches())
