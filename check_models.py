import sys, os
sys.path.insert(0, '/home/irfan/chimera')
os.chdir('/home/irfan/chimera')

import time
from chimera.providers.catalogue import PROVIDER_CATALOGUE, PROVIDER_ENABLED
from chimera.providers.auto_models import DISCOVERED, effective_models

now = int(time.time())
seen = {}
duplicates = []

for p in PROVIDER_CATALOGUE:
    if not PROVIDER_ENABLED.get(p["name"], True):
        continue
    has_key = bool(p.get("api_key"))
    is_keyless = p.get("keyless", False)
    status = "✅" if (has_key or is_keyless) else "❌"
    
    for bucket in ("non_reasoning", "reasoning"):
        for m in effective_models(p, bucket):
            # Check if model already appears under another provider
            base_id = m.split("/")[-1]  # strip any prefix
            if base_id in seen:
                duplicates.append({
                    "model": base_id,
                    "providers": [seen[base_id], p["name"]],
                    "status": status
                })
            else:
                seen[base_id] = p["name"]

print("=== PROVIDERS WITH/WITHOUT API KEYS ===")
provider_status = {}
for p in PROVIDER_CATALOGUE:
    has_key = bool(p.get("api_key"))
    is_keyless = p.get("keyless", False)
    ok = has_key or is_keyless
    provider_status[p["name"]] = ok
    marker = "✅" if ok else "❌"
    print(f"{marker} {p['name']:20s} api_key={'yes' if has_key else 'no':3s} keyless={'yes' if is_keyless else 'no'}")

print(f"\n=== DUPLICATE MODEL NAMES (same model under multiple providers) ===")
print(f"Total unique model names: {len(seen)}")
print(f"Total providers: {len(PROVIDER_CATALOGUE)}")
print(f"Providers WITH keys: {sum(1 for v in provider_status.values() if v)}")
print(f"Providers WITHOUT keys: {sum(1 for v in provider_status.values() if not v)}")

print("\nFirst 20 duplicates:")
for d in duplicates[:20]:
    print(f"  '{d['model']}' appears in: {d['providers']}")