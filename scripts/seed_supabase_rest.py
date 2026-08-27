import asyncio
import json
import httpx
from sqlalchemy import text
from core.db import AsyncSessionLocal

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://ovkrhkfhscsyxixsxenk.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_KEY", "")

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=ignore-duplicates"
}

async def seed_via_rest():
    async with AsyncSessionLocal() as session:
        # 1. lines 시딩
        print("Fetching lines from local SQLite...")
        lines = (await session.execute(text("SELECT * FROM lines ORDER BY id"))).mappings().all()
        line_dicts = [dict(r) for r in lines]
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            # 100개씩 PostgREST 배치 전송
            batch_size = 100
            for i in range(0, len(line_dicts), batch_size):
                batch = line_dicts[i:i+batch_size]
                res = await client.post(f"{SUPABASE_URL}/rest/v1/lines", headers=headers, json=batch)
                print(f"Lines batch {i//batch_size + 1}: status {res.status_code}")
                if res.status_code >= 400:
                    print(f"Error: {res.text}")
                    return

            # 2. interpretation_chunks 시딩
            print("Fetching interpretation_chunks from local SQLite...")
            chunks = (await session.execute(text("SELECT * FROM interpretation_chunks ORDER BY id"))).mappings().all()
            chunk_dicts = []
            for r in chunks:
                d = dict(r)
                if isinstance(d.get("embedding"), str):
                    d["embedding"] = json.loads(d["embedding"])
                chunk_dicts.append(d)
                
            print(f"Total chunks: {len(chunk_dicts)}")
            chunk_batch_size = 50
            for i in range(0, len(chunk_dicts), chunk_batch_size):
                batch = chunk_dicts[i:i+chunk_batch_size]
                res = await client.post(f"{SUPABASE_URL}/rest/v1/interpretation_chunks", headers=headers, json=batch)
                print(f"Chunks batch {i//chunk_batch_size + 1}/{(len(chunk_dicts)-1)//chunk_batch_size + 1}: status {res.status_code}")
                if res.status_code >= 400:
                    print(f"Error: {res.text}")
                    return

        print("Seeding completed successfully via Supabase REST API!")

if __name__ == "__main__":
    asyncio.run(seed_via_rest())
