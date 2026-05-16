import sys, os, json, asyncio, httpx
sys.path.insert(0, '/home/irfan/chimera')
os.chdir('/home/irfan/chimera')

async def t():
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.get("http://localhost:8001/v1/models")
        d = r.json()
        print(f'Total models in /v1/models: {d["total"]}')
        
        # OpenRouter models
        or_models = [m for m in d['data'] if m['provider'] == 'openrouter']
        print(f'\nOpenRouter models: {len(or_models)}')
        print('First 15:')
        for m in or_models[:15]:
            print(f'  {m["id"]}')
        
        # Models with >1 slash (potential double prefix)
        multi = [m for m in d['data'] if m['id'].count('/') > 1]
        print(f'\nMulti-slash (>1 slash): {len(multi)}')
        for m in multi[:15]:
            print(f'  [{m["provider"]:12s}] {m["id"]}')
        
        # Show providers with no API key that still appear in /v1/models
        print('\n=== Providers with no API key but still in /v1/models ===')
        keyless_providers = {'pollinations', 'ollama', 'llm7'}
        no_key_providers = {'a4f', 'huggingface', 'sambanova', 'together', 'mistral', 'xai',
                           'deepseek', 'perplexity', 'fireworks', 'deepinfra', 'minimax'}
        
        for prov in sorted(set(keyless_providers | no_key_providers)):
            models = [m['id'] for m in d['data'] if m['provider'] == prov]
            if models:
                print(f'  {prov} ({len(models)} models): {models[:3]}')

asyncio.run(t())