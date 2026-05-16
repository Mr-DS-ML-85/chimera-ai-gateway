import sys, os, asyncio
sys.path.insert(0, '/home/irfan/chimera')
os.chdir('/home/irfan/chimera')

# Simulate the exact list_models logic
from chimera.providers.catalogue import PROVIDER_CATALOGUE, PROVIDER_ENABLED
from chimera.providers.auto_models import DISCOVERED, effective_models

name = 'groq'
p = next(pr for pr in PROVIDER_CATALOGUE if pr['name'] == 'groq')

print("=== SIMULATING list_models for groq ===")
print(f"p.get('keyless') = {p.get('keyless')}")
print(f"p.get('api_key') = {bool(p.get('api_key'))}")
print(f"Groq in DISCOVERED: {'groq' in DISCOVERED}")
print(f"Groq DISCOVERED models: {DISCOVERED.get('groq', {})}")
print()

for bucket in ('non_reasoning', 'reasoning'):
    print(f"--- bucket: {bucket} ---")
    for m in effective_models(p, bucket):
        prefix_stripped = m
        
        # Apply all stripping logic
        if m.startswith(f"{name}/"):
            remainder = m[len(name) + 1:]
            print(f"  m={m!r} -> starts with groq/ -> remainder={remainder!r}")
            while True:
                stripped_again = False
                for _org in ("qwen", "openai", "anthropic", "meta-llama",
                              "deepseek", "google", "mistralai", "cohere",
                              "microsoft", "nvidia", "01-ai", "baai",
                              "bytedance", "ibm", "moonshotai", "z-ai"):
                    if remainder.startswith(f"{_org}/"):
                        old_rem = remainder
                        remainder = remainder[len(_org) + 1:]
                        print(f"    strip {_org}/ -> {old_rem!r} -> {remainder!r}")
                        stripped_again = True
                        break
                if not stripped_again:
                    break
            prefix_stripped = remainder if remainder else m
        
        prefixed = f"{name}/{prefix_stripped}"
        slashes = prefixed.count('/')
        marker = ' ⚠️' if slashes > 1 else ''
        print(f"  => {prefixed}{marker}")
    print()