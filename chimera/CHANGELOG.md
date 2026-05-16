# Changelog — Chimera Gateway

All notable changes to this project are documented here. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [8.2.0] — 2026-05-16

### Added
- **gemini-3.1-flash-lite** support — added to Google provider catalogue and model alias system
- **Custom model aliases via `MODEL_ALIASES_JSON`** — add aliases in `.env` without modifying code
- **SSL/TLS support** — built-in HTTPS with self-signed certs for Claude Desktop compatibility
- **`SSL_CERT_FILE` / `SSL_KEY_FILE`** — env vars to configure TLS certificate paths
- **22 providers fully configured** — MiniMax as provider #22
- `docs/PROVIDERS.md` — comprehensive provider documentation
- `docs/SECURITY.md` — security policy and threat model documentation

### Changed
- **README.md** fully updated with TLS setup instructions, custom aliases, and provider docs
- **Model name rewriting** — `gemini-3-flash` now routes to `google/gemini-3-flash-preview-05-20` (direct Google), not `opencode-zen`
- **README.md** — clone URL: `github.com/Mr-DS-ML-85/chimera-ai-gateway`
- **README.md** — provider count: `22` across all badges and descriptions
- **README.md** — `.env` config section expanded with SSL and custom alias examples
- **README.md** — Docker section now exposes both port 8000 (HTTP) and 8443 (HTTPS)
- **README.md** — Claude Desktop section added HTTPS warning and dual URL examples
- **README.md** — Model alias table updated with `gemini-3.1-flash-lite` and `claude-4.6-sonnet`
- **README.md** — Architecture diagram references v8.2.0

### Fixed
- **`CUSTOM_MODEL_ALIASES` not imported** in `api/routes/chat.py` — caused `NameError` on requests
- **Google gemini model routing** — `_infer_provider_affinity()` now recognizes bare `gemini-*` model names
- **google provider live discovery** — confirmed 44 models discovered from `generativelanguage.googleapis.com`
- **gemini-3.1-flash-lite not in catalogue** — added to `non_reasoning_models` list
- **Port conflict on restart** — server now handles `Address already in use` gracefully

### Security
- Content Policy: `scan()` functions redefined for correct CSAM/WMD/Self-harm blocking
- WAF hardened against non-ASCII bypass (LDAP Unicode rule) and improved SQLi/CMDi/XSS rules
- SSRF protection: `follow_redirects` disabled globally in `httpx` client
- Admin API CRUD methods restored in `keys/virtual_keys.py`
- Mass Assignment Guard: `role: system` now correctly allowed for legitimate system prompts
- `.gitignore` updated to exclude `*.pem`, `cert.pem`, `key.pem`

### Infrastructure
- **docker-compose.yml** — `MODEL_ALIASES_JSON` env var passed through to container
- **`.env`** — `SSL_CERT_FILE`, `SSL_KEY_FILE`, `MODEL_ALIASES_JSON` config added
- **`.env.example`** — `GATEWAY_VERSION=8.2.0` consistent with `__init__.py`

---

## [8.1.x] — 2025 (minor releases)

> Minor releases focused on provider additions, bug fixes, and documentation improvements.

### [8.1.4] — 2025-05-10
- Fixed provider catalogue pagination issues
- Improved auto-model discovery error handling

### [8.1.3] — 2025-05-08
- Added additional fallback routing for edge case models
- Improved latency tracking with EMA calculation

### [8.1.2] — 2025-05-05
- Fixed rate limiter memory leak under high load
- Improved circuit breaker reset logic

### [8.1.1] — 2025-05-03
- Bug fixes for virtual key validation
- Improved error messages for missing provider keys

### [8.1.0] — 2025-05-01
- Added OpenCode Zen provider support
- Model name rewriting for Claude Desktop compatibility

---

## [8.0.0] — 2025-01 — Major Feature Release

### Added
- **16+ new AI providers** — Mistral AI, xAI/Grok, DeepSeek, Perplexity, Fireworks AI, DeepInfra, and more
- **Live model auto-discovery system** — hourly refresh from each provider's `/models` endpoint
- **Dynamic model classification** — automatic routing into `reasoning` and `non_reasoning` buckets
- **Virtual model routing** — `non-reasoning-auto` and `reasoning-auto` aliases
- **AES-256-GCM end-to-end encryption (E2EE)** for responses
- **HMAC request signing** for outbound traffic integrity
- **Transparency log** — append-only SHA-256 audit trail
- **Response deduplication** via SHA-256 rolling window
- **Tool call depth limits** (max 3 per response)
- **Canary token system** for secret/API key exfiltration detection
- **Redis-backed nonce registry** for replay attack protection
- **Custom OpenAI-compatible BYOK endpoint** support
- **MiniMax provider** support (text and image URLs, no Base64 inline images)

### Changed
- Provider catalogue expanded from 5 to 21+ providers
- Virtual keys system for scoped API key management
- Circuit breaker implementation per provider
- Latency-aware routing (Exponential Moving Average)
- PII redaction in requests and responses
- Version number aligned: `8.0.0` in `__init__.py`, `.env.example`, and README

### Security
- **AC-1**: Payload injection detection (pattern matching + base64 nested scan)
- **AC-2**: Canary token regex scanner for secret exfiltration
- **WAF**: SQLi, XSS, CMDi, path traversal, encoded bypass blocking
- **Prompt Shield**: multi-shot injection, role confusion detection
- **SSRF protection**: blocks localhost, 169.254.x.x, metadata service
- **Output Guard**: validates tool call structure and response schema
- **Content Policy**: CSAM, WMD, self-harm blocking

---

## [7.x] — 2024 — Prior Releases

### [7.5.0] — 2024-11
- Added Cloudflare Workers AI provider
- Basic circuit breaker implementation

### [7.4.0] — 2024-10
- Added Pollinations.AI provider
- Basic virtual key system

### [7.3.0] — 2024-09
- Added OpenRouter provider
- Introduced virtual model aliases

### [7.2.0] — 2024-08
- Added Groq provider
- Basic rate limiting

### [7.1.0] — 2024-07
- Added Google AI Studio provider
- PII redaction framework

### [7.0.0] — 2024-06 — Initial Major Release
- OpenAI-compatible gateway
- Basic provider routing
- 5 initial providers: Groq, Google, OpenRouter, Pollinations, Ollama

---

## Upgrade Notes

### v8.1 → v8.2
- No breaking API changes
- `gemini-3-flash` now routes via `google/gemini-3-flash-preview-05-20` (direct Google AI Studio)
- If using `gemini-3-flash`, ensure `GOOGLE_API_KEY` is set in `.env`
- New `MODEL_ALIASES_JSON` env var for custom aliases without code changes
- New `SSL_CERT_FILE` / `SSL_KEY_FILE` env vars for TLS (optional)
- MiniMax provider: add `MINIMAX_API_KEY` if using MiniMax
- Version now consistent: `8.2.0` in `__init__.py`, `.env.example`, and README

### v8.0 → v8.1
- No breaking API changes
- OpenCode Zen provider requires `OPENCODE_ZEN_API_KEY` in `.env`

### Pre-v8.0
- v8.0 was a significant rewrite. The FastAPI app, routing engine, and security layers were redesigned.
- Review the v7 → v8 migration guide in docs/ before upgrading from pre-8.0 releases.
- Virtual keys format changed from flat dict to structured JSON
- Provider catalogue format changed to structured provider definitions