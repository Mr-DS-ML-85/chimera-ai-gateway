import sys, os, asyncio, httpx
sys.path.insert(0, '/home/irfan/chimera')
os.chdir('/home/irfan/chimera')

async def t():
    c = httpx.AsyncClient(timeout=15.0)
    r = await c.get("http://localhost:8001/debug/discovered")
    d = r.json()
    print("DISCOVERED keys:", d['DISCOVERED_keys'])
    for key, models in d['DISCOVERED'].items():
        print(f"  {key}: {models}")

asyncio.run(t())