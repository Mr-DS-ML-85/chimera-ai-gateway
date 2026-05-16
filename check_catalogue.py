import sys, os
sys.path.insert(0, '/home/irfan/chimera')
os.chdir('/home/irfan/chimera')

from chimera.providers.catalogue import PROVIDER_CATALOGUE
for p in PROVIDER_CATALOGUE:
    has_key = bool(p.get('api_key'))
    models = p.get("non_reasoning_models", [])[:5]
    print(f"[{'✅' if has_key else '❌'}] {p['name']:20s}: {models}")