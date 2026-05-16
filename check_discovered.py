import sys, os
sys.path.insert(0, '/home/irfan/chimera')
os.chdir('/home/irfan/chimera')

from chimera.providers.auto_models import DISCOVERED

print("=== DISCOVERED (live) models per provider ===")
for prov, buckets in sorted(DISCOVERED.items()):
    print(f"\n{prov}:")
    for bucket, models in buckets.items():
        print(f"  {bucket}: {models[:5]}")