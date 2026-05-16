import sys, os, json, asyncio, httpx
sys.path.insert(0, '/home/irfan/chimera')
os.chdir('/home/irfan/chimera')

async def t():
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.get("http://localhost:8001/v1/models")
        d = r.json()
        
        # Check Groq models - are they multi-slash or clean?
        groq_models = [m['id'] for m in d['data'] if m['provider'] == 'groq']
        print(f'Groq ({len(groq_models)} models):')
        for m in groq_models[:10]:
            slash_count = m.count('/')
            marker = ' ⚠️' if slash_count > 1 else ''
            print(f'  x{slash_count} {m}{marker}')
        
        # Check NVIDIA models
        nvidia_models = [m['id'] for m in d['data'] if m['provider'] == 'nvidia']
        print(f'\nNVIDIA ({len(nvidia_models)} models):')
        multi_nvidia = [m for m in nvidia_models if m.count('/') > 1]
        print(f'  Multi-slash: {len(multi_nvidia)}')
        for m in multi_nvidia[:5]:
            print(f'  ⚠️ {m}')
        
        # Check Cloudflare models
        cf_models = [m['id'] for m in d['data'] if m['provider'] == 'cloudflare']
        multi_cf = [m for m in cf_models if m.count('/') > 1]
        print(f'\nCloudflare ({len(cf_models)} models):')
        print(f'  Multi-slash: {len(multi_cf)}')
        for m in multi_cf[:3]:
            print(f'  ⚠️ {m}')

asyncio.run(t())