import sys, os, asyncio, httpx
sys.path.insert(0, '/home/irfan/chimera')
os.chdir('/home/irfan/chimera')

async def t():
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.get("http://localhost:8001/v1/models")
        d = r.json()
        multi = [m for m in d['data'] if m['id'].count('/') > 1]
        print(f'Multi-slash models ({len(multi)} total):')
        from collections import Counter
        by_provider = Counter(m['provider'] for m in multi)
        print(f'  By provider: {dict(sorted(by_provider.items()))}')
        print('  Sample (first 3 per provider):')
        for prov in sorted(set(m['provider'] for m in multi)):
            samples = [m['id'] for m in multi if m['provider'] == prov][:3]
            print(f'    {prov}: {samples}')

asyncio.run(t())