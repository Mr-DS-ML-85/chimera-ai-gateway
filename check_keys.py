import sys, os
sys.path.insert(0, '/home/irfan/chimera')
os.chdir('/home/irfan/chimera')

from chimera.core import config

# Get all uppercase vars that look like API keys
attrs = [a for a in dir(config) if a.endswith('_API_KEY') or a.endswith('_KEY')]
for k in sorted(attrs):
    v = getattr(config, k, '')
    status = '✅' if v else '❌'
    preview = repr(v[:6]) if v else '(not set)'
    print(f'{status} {k:30s}: {preview}')