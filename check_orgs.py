import sys, os, asyncio, httpx
sys.path.insert(0, '/home/irfan/chimera')
os.chdir('/home/irfan/chimera')

async def t():
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.get("http://localhost:8001/v1/models")
        d = r.json()
        
        # Get all multi-slash models and find their first segments
        multi = [m['id'] for m in d['data'] if m['id'].count('/') > 1]
        print(f'Total multi-slash: {len(multi)}')
        
        from collections import Counter
        first_segs = Counter(m.split('/')[0] for m in multi)
        print(f'\nFirst segments needing ORG_PREFIXES:')
        for seg, cnt in sorted(first_segs.items()):
            print(f'  "{seg}" ({cnt} models)')
        
        print(f'\nFull list of first segments not in current ORG_PREFIXES:')
        current = {"01-ai","abacusai","adept","ai21labs","aisingapore","alibaba","bigcode",
                   "cohere","databricks","deepinfra-ai","deepmind","microsoft","mistralai",
                   "nvidia","openai","openchat","presto","qwen","recurshy","sambaNova",
                   "snorkel","stabilityai","tiiuae","togetherai","upstage","writer",
                   "zhipuai","sarvamai","stepfun-ai","stockmark","@cf"}
        for seg, cnt in sorted(first_segs.items()):
            if seg not in current:
                print(f'  "{seg}",  # {cnt} models')

asyncio.run(t())