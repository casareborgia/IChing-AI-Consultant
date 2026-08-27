import asyncio
from sqlalchemy import text
from core.db import AsyncSessionLocal

def escape_sql_str(val):
    if val is None:
        return "NULL"
    # replace single quote with two single quotes
    escaped = val.replace("'", "''")
    return f"'{escaped}'"

async def split_lines():
    async with AsyncSessionLocal() as session:
        line_rows = (await session.execute(text("SELECT * FROM lines ORDER BY id"))).mappings().all()
        
        batch_size = 100
        for i in range(0, len(line_rows), batch_size):
            slice_rows = line_rows[i:i+batch_size]
            line_values = []
            for r in slice_rows:
                st_text = escape_sql_str(r['statement_text'])
                st_ko = escape_sql_str(r['statement_ko'])
                s_xiang = escape_sql_str(r['small_xiang_text'])
                v = f"({r['id']}, {r['hexagram_id']}, {r['line_number']}, {st_text}, {st_ko}, {s_xiang})"
                line_values.append(v)
            
            sql = f"INSERT INTO public.lines (id, hexagram_id, line_number, statement_text, statement_ko, small_xiang_text) VALUES {','.join(line_values)} ON CONFLICT (id) DO NOTHING;"
            with open(f"scripts/supabase_batches/02_lines_part_{i//batch_size + 1}.sql", "w", encoding="utf-8") as f:
                f.write(sql)
                
    print("Regenerated 02_lines_part_*.sql files")

if __name__ == "__main__":
    asyncio.run(split_lines())
