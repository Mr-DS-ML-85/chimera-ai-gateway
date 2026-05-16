from fastapi import Request, FastAPI
from fastapi.responses import JSONResponse
import os
import logging
import httpx

app = FastAPI()
logging.basicConfig(level=logging.INFO)

# WAF bypass middleware
@app.middleware("http")
async def waf_bypass_middleware(request: Request, call_next):
    path = request.url.path.lower()
    content_type = request.headers.get("content-type", "").lower()
    bypass_patterns = ["ldap", "xml", "/v1/models"]
    
    for pattern in bypass_patterns:
        if pattern in path or pattern in content_type:
            request.state.waf_bypassed = True
            logging.info(f"WAF bypassed for: {path}")
            break
    
    return await call_next(request)

# /v1/models with fallback
@app.get("/v1/models")
async def list_models():
    fallback_models = ["sonnet", "haiku", "opus", "claude-4.6-sonnet"]
    if not hasattr(app.state, "models") or not app.state.models.get("data"):
        return {"data": [{"id": model} for model in fallback_models]}
    return app.state.models

# Chat completions - route to OpenCode provider
@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    try:
        body = await request.json()
        model = body.get("model", "sonnet")
        messages = body.get("messages", [])
        
        logging.info(f"Chat request: model={model}")
        
        # Route to OpenCode API
        api_key = os.getenv("OPENCODE_API_KEY", "fake-key")
        base_url = os.getenv("OPENCODE_BASE_URL", "https://api.opencode.ai/v1")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                json={"model": model, "messages": messages},
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=30.0
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                # Fallback mock response
                return {
                    "choices": [{
                        "message": {
                            "role": "assistant",
                            "content": f"Response from {model} — API status: {response.status_code}"
                        }
                    }]
                }
    except Exception as e:
        logging.error(f"Chat error: {e}")
        return {
            "choices": [{
                "message": {
                    "role": "assistant", 
                    "content": f"Error: {str(e)}"
                }
            }]
        }

# Health check
@app.get("/health")
async def health():
    return {"status": "ok"}