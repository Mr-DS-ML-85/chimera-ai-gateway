import sys, os, json, asyncio, httpx
sys.path.insert(0, '/home/irfan/chimera')
os.chdir('/home/irfan/chimera')

from chimera.providers.catalogue import PROVIDER_CATALOGUE, PROVIDER_ENABLED
from chimera.providers.auto_models import DISCOVERED, effective_models

print("=== PROVIDER_CATALOGUE (static) vs DISCOVERED (live) ===\n")

# Check which providers have live models
for p in PROVIDER_CATALOGUE:
    name = p['name']
    has_key = bool(p.get('api_key'))
    is_keyless = p.get('keyless', False)
    
    # Check DISCOVERED
    in_discovered = name in DISCOVERED
    
    # Get static models
    static = p.get('non_reasoning_models', []) + p.get('reasoning_models', [])
    
    # Get effective (live if available, static otherwise)
    effective_non = effective_models(p, 'non_reasoning')
    effective_reasoning = effective_models(p, 'reasoning')
    effective_all = effective_non + effective_reasoning
    
    # Check for multi-segment models (potential double prefix issue)
    multi_static = [m for m in static if '/' in m]
    multi_effective = [m for m in effective_all if '/' in m]
    
    ok = has_key or is_keyless
    marker = '✅' if ok else '❌'
    
    print(f"{marker} {name:15s} DISCOVERED={in_discovered} | key={has_key} keyless={is_keyless}")
    print(f"  Static: {len(static)} models, {len(multi_static)} multi-segment")
    print(f"  Effective: {len(effective_all)} models, {len(multi_effective)} multi-segment")
    if multi_static:
        print(f"  Static multi-segment samples: {multi_static[:5]}")
    if multi_effective:
        print(f"  Effective multi-segment samples: {multi_effective[:5]}")
    print()