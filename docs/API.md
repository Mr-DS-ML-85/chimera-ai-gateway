# API Reference — Chimera Gateway v8.2.0

Full reference for all Chimera Gateway endpoints.

---

## Authentication

All endpoints accept Bearer token authentication:

```
Authorization: Bearer <your-key>
```

Keys supported:
- **Master key** — `CHIMERA_API_KEY` from `.env`
- **Virtual keys** — scoped keys created via admin API
- **No auth** — works if `CHIMERA_API_KEY` is unset (dev mode)

---

## `POST /v1/chat/completions`

OpenAI-compatible chat completions endpoint.

**Request body:**

```json
{
  "model": "auto",
  "messages": [
    { "role": "system", "content": "You are a helpful assistant." },
    { "role": "user", "content": "Hello!" }
  ],
  "temperature": 0.7,
  "max_tokens": 1024,
  "stream": false,
  "top_p": 1.0,
  "stop": null,
  "presence_penalty": 0.0,
  "frequency_penalty": 0.0,
  "user": "user-123",
  "reasoning": null,
  "encrypt": false
}
```

**Chimera-specific extra fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `reasoning` | `bool \| null` | `null` | Force reasoning model routing |
| `encrypt` | `bool` | `false` | Encrypt response with AES-256-GCM |

**Response (non-streaming):**

```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "created": 1715000000,
  "model": "auto",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Hello! How can I help you today?"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 12,
    "completion_tokens": 10,
    "total_tokens": 22
  }
}
```

**Response headers:**

```
X-Provider: groq
X-Request-ID: uuid-here
X-Gateway-Version: 8.2.0
```

---

## `POST /v1/messages`

Anthropic-native messages endpoint for Claude Code and Claude SDK compatibility.

**Request body:**

```json
{
  "model": "auto:reasoning",
  "messages": [
    { "role": "user", "content": "Hello!" }
  ],
  "max_tokens": 1024,
  "temperature": null,
  "stream": false,
  "system": null,
  "thinking": null,
  "top_k": null,
  "top_p": null,
  "stop_sequences": null
}
```

**Virtual model aliases (same as `/v1/chat/completions`):**
- `auto`, `auto:free`, `auto:reasoning`, `auto:free:reasoning`
- `fast`, `fast:free`, `quality`, `balanced`
- `reasoning`, `reasoning:free`, `non-reasoning`, `non-reasoning:free`

**Model alias normalization:**
- `sonnet` → `anthropic/claude-sonnet-4-7`
- `opus` → `anthropic/claude-opus-4-5`
- `haiku` → `anthropic/claude-haiku-4-7`

**Anthropic headers forwarded:**
- `anthropic-beta` — enables beta features
- `anthropic-version` — specifies API version (e.g. `2023-06-01`)
- `anthropic-dangerous-direct-browser-access` — for direct browser clients

**Direct Anthropic routing:** When `ANTHROPIC_API_KEY` is set in `.env` and the model starts with `anthropic/` (or normalizes to an Anthropic model), the request is routed directly to the Anthropic API — bypassing OpenAI-compatible providers.

**Response (non-streaming):**

```json
{
  "id": "msg_abc123",
  "type": "message",
  "role": "assistant",
  "model": "auto:reasoning",
  "content": [{ "type": "text", "text": "Hello! How can I help?" }],
  "stop_reason": "end_turn",
  "stop_sequence": null,
  "usage": {
    "input_tokens": 12,
    "output_tokens": 10,
    "cache_creation_input_tokens": 0,
    "cache_read_input_tokens": 0
  }
}
```

**Response (streaming):** `text/event-stream` with SSE chunks in Anthropic format:

```
data: {"type":"message_start","message":{"id":"msg_abc","type":"message","role":"assistant","model":"auto","usage":{"input_tokens":0,"output_tokens":0}}}

data: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}

data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Hello"}}

data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"!"}}

data: {"type":"content_block_stop","index":0}

data: {"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":10}}

data: {"type":"message_stop"}
```

---

## `POST /v1/messages/count_tokens`

Claude Code pre-flight token counting. Returns estimated token count for a request body without making an LLM call.

**Request body:** Same as `/v1/messages`.

**Response:**

```json
{
  "tokens": 42,
  "count_tokens_version": "1"
}
```

**Note:** Estimation uses ~1 token per 4 characters (conservative for Claude tokenization). For exact counts, use the direct Anthropic API.

---

## `POST /v1/responses`

[Responses API](https://docs.anthropic.com/en/api/responses) format wrapper. Translates to OpenAI format internally, routes via the same engine.

**Request body:**

```json
{
  "model": "auto",
  "input": [
    { "role": "user", "content": "Hello!" }
  ],
  "max_tokens": 1024,
  "stream": false
}
```

**Response:** OpenAI-format chat completion (normalised from provider).

---

## `GET /v1/models`

Lists all available models from all providers, plus virtual routing aliases.

**Response:**

```json
{
  "object": "list",
  "data": [
    {
      "id": "groq/llama-3.3-70b-versatile",
      "object": "model",
      "created": 1715000000,
      "owned_by": "groq",
      "provider": "groq",
      "type": "non_reasoning",
      "source": "live"
    },
    {
      "id": "auto/auto",
      "object": "model",
      "created": 1715000000,
      "owned_by": "gateway",
      "provider": "auto",
      "type": "non_reasoning",
      "source": "virtual"
    }
  ],
  "total": 247
}
```

**Model sources:**
- `live` — discovered at runtime from provider API
- `static` — from static catalogue fallback
- `virtual` — gateway routing aliases (e.g. `auto/auto`, `groq/auto`)

---

## `GET /v1/health`

System health check with per-provider status.

**Response:**

```json
{
  "status": "ok",
  "version": "8.2.0",
  "waf_rule_version": "1.0.0",
  "config_fingerprint": "sha256:abc123...",
  "e2ee_fingerprint": "sha256:def456...",
  "providers": [
    {
      "name": "groq",
      "enabled": true,
      "circuit_state": "CLOSED",
      "exhausted": false,
      "ema_latency_ms": 387.4,
      "model_source": "live"
    }
  ],
  "ts": "2024-05-15T10:30:00Z"
}
```

**Status codes:**
- `200` — at least one provider healthy
- `503` — all providers degraded/exhausted

**Circuit states:** `CLOSED` (normal), `OPEN` (failing), `HALF_OPEN` (testing recovery)

---

## `GET /v1/metrics`

Prometheus-compatible plain-text metrics.

**Response:**

```
# HELP chimera_provider_requests_total Total provider requests
# TYPE chimera_provider_requests_total counter
chimera_provider_requests_total{provider="groq"} 42
chimera_provider_requests_total{provider="openrouter"} 18

# HELP chimera_provider_ema_latency_ms EMA latency in milliseconds
# TYPE chimera_provider_ema_latency_ms gauge
chimera_provider_ema_latency_ms{provider="groq"} 387.4
chimera_provider_ema_latency_ms{provider="openrouter"} 892.1

# HELP chimera_provider_exhausted Provider exhausted flag
# TYPE chimera_provider_exhausted gauge
chimera_provider_exhausted{provider="groq"} 0
chimera_provider_exhausted{provider="openrouter"} 0

# HELP chimera_waf_blocks_total WAF blocks
# TYPE chimera_waf_blocks_total counter
chimera_waf_blocks_total{category="sqli"} 2
```

---

## `GET /v1/transparency-log`

Append-only SHA-256 audit log of recent requests.

**Query parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | `int` | `100` | Max entries to return (1–1000) |
| `offset` | `int` | `0` | Pagination offset |

**Response:**

```json
{
  "entries": [
    {
      "ts": "2024-05-15T10:30:00Z",
      "req_hash": "sha256:abc123...",
      "resp_hash": "sha256:def456...",
      "provider": "groq",
      "model": "llama-3.3-70b-versatile",
      "tokens_in": 12,
      "tokens_out": 10,
      "latency_ms": 387,
      "blocked": false
    }
  ],
  "total": 10000,
  "cap": 10000
}
```

---

## `GET /v1/usage`

Per-provider token/request counters with EMA latency. Resets daily.

**Response:**

```json
{
  "providers": {
    "groq": {
      "requests_today": 42,
      "tokens_in_today": 504,
      "tokens_out_today": 420,
      "avg_latency_ms": 387.4
    }
  }
}
```

---

## Admin Endpoints — `POST /v1/admin/*`

### `POST /v1/admin/keys`

Create a new scoped virtual key.

**Request:**

```json
{
  "key_id": "my-app-key",
  "description": "My application",
  "rate_limit_rpm": 60,
  "allowed_models": ["auto", "groq/*"],
  "allowed_providers": ["groq", "openrouter"]
}
```

**Response:** `201 Created` with the new key secret.

### `GET /v1/admin/keys`

List all virtual keys (metadata only, secrets redacted).

### `DELETE /v1/admin/keys/{key_id}`

Revoke a virtual key.

### `POST /v1/admin/providers/{name}/enable`

Enable a provider that was disabled by the circuit breaker.

### `POST /v1/admin/providers/{name}/disable`

Manually disable a provider.

---

## Error Responses

All errors return JSON with a consistent shape:

**Format:**

```json
{
  "error": "error_code",
  "message": "Human-readable description",
  "details": {}
}
```

**Common error codes:**

| HTTP Status | Error Code | Description |
|-------------|------------|-------------|
| `400` | `waf_blocked` | WAF pattern match (SQLi, XSS, etc.) |
| `400` | `prompt_injection_blocked` | Prompt shield detected injection |
| `400` | `content_policy_violation` | CSAM, WMD, or self-harm content |
| `400` | `request_contains_disallowed_patterns` | Canary token match (key exfil) |
| `401` | — | Missing or invalid Authorization header |
| `403` | — | Invalid API key |
| `413` | — | Request body too large |
| `429` | — | Rate limit exceeded |
| `451` | `content_policy_violation` | Content policy violation |
| `502` | `upstream_error` | Provider returned an error |
| `503` | — | No providers support the requested capabilities |

---

## WebSocket Streaming

Streaming is supported on both `/v1/chat/completions` and `/v1/messages` via `stream: true`.

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "auto", "messages": [{"role": "user", "content": "Count to 5"}], "stream": true}'
```

**Response:** `text/event-stream` with SSE chunks:

```
data: {"id":"chatcmpl-abc","object":"chat.completion.chunk","created":1715000000,"model":"auto","choices":[{"index":0,"delta":{"content":"1"},"finish_reason":null}]}

data: {"id":"chatcmpl-abc","object":"chat.completion.chunk","created":1715000000,"model":"auto","choices":[{"index":0,"delta":{"content":"2"},"finish_reason":null}]}

data: [DONE]
```

---

## Rate Limits

| Limit Type | Default | Scope |
|------------|---------|-------|
| Global IP | 60 RPM | Per IP address |
| Per-user (master key) | 120 RPM | Per authenticated key |
| Per-virtual-key | Configurable | Per key |
| Per-provider | Varies | See provider matrix |

Rate limit headers on responses:

```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1715000060
Retry-After: 3
```