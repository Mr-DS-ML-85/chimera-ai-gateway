import sys, os
sys.path.insert(0, '/home/irfan/chimera')
os.chdir('/home/irfan/chimera')

import inspect
from chimera.api.routes.models import list_models
src = inspect.getsource(list_models)

lines = src.split('\n')
for i, line in enumerate(lines):
    if 'stripped_again' in line or 'remainder.startswith' in line or 'meta-llama' in line:
        print(f'Line {i}: {line}')