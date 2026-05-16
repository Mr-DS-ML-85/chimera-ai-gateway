import sys, os, asyncio, httpx
sys.path.insert(0, '/home/irfan/chimera')
os.chdir('/home/irfan/chimera')

async def t():
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.get("http://localhost:8001/v1/models")
        d = r.json()
        
        # For each multi-slash model, trace which stripping rule should fix it
        from collections import Counter
        
        # Check what should have been stripped but wasn't
        providers_to_check = {
            'nvidia': ['google', 'baai', 'bytedance', 'ibm', 'minimaxai', 'moonshotai', 'nv-mistralai', 'z-ai', 'zyphra'],
            'cloudflare': ['deepseek-ai', 'qwen'],
            'groq': ['meta-llama', 'openai', 'qwen'],
        }
        
        multi = [m['id'] for m in d['data'] if m['id'].count('/') > 1]
        
        print(f'Total multi-slash: {len(multi)}')
        print()
        
        for prov, orgs in providers_to_check.items():
            print(f'=== {prov} ===')
            for org in orgs:
                models = [m for m in multi if m.startswith(f'{prov}/{org}/')]
                if models:
                    print(f'  "{org}/" -> {len(models)} models')
                    for m in models[:3]:
                        print(f'    {m}')
            print()

asyncio.run(t())