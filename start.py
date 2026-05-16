#!/usr/bin/env python3
import sys
# Set up PYTHONPATH before any other imports
sys.path.insert(0, '/home/irfan/chimera/chimera')  # so 'api' resolves
sys.path.insert(0, '/home/irfan/chimera')           # so 'chimera' resolves

import os
os.environ['DEV'] = '1'

import uvicorn
from main import app

if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000, log_level='error')