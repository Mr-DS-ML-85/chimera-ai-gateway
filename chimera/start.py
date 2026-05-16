# Chimera Startup Script

import sys
import os
# Set up PYTHONPATH
sys.path.insert(0, '/home/irfan/chimera/chimera')
sys.path.insert(0, '/home/irfan/chimera')

# Load .env early
from dotenv import load_dotenv
load_dotenv()

os.environ['DEV'] = '1'

# Load FastAPI and WAF bypass
from fastapi import FastAPI
from chimera.router import app
from chimera.waf_bypass import waf_bypass_middleware
app.middleware("http")(waf_bypass_middleware)

# Load model aliases
import json
model_aliases = json.loads(os.getenv("MODEL_ALIASES_JSON", '{}'))
app.state.models = {"data": [{"id": alias} for alias in model_aliases.keys()]}

# Fallback models (Groq, GPT-OSS, etc.)
fallback_models = ["sonnet", "haiku", "opus", "claude-4.6-sonnet", "gpt-oss", "groq/llama"]
if not app.state.models["data"]:
    app.state.models = {"data": [{"id": model} for model in fallback_models]}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000, log_level='error')