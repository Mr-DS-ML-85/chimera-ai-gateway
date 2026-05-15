# Changelog — Chimera Gateway

All notable changes to this project are documented here. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [8.2.0] — 2025-05-15

### Added
- **22 providers** now fully configured (added MiniMax as provider #22)
- `docs/PROVIDERS.md` — comprehensive provider documentation with all 22 endpoints, free tiers, rate limits, and setup instructions
- `docs/SECURITY.md` — detailed security policy and threat model documentation
- `CHANGELOG.md` — project changelog
- **MiniMax provider** — supports text and image URLs (no Base64 inline images)

### Changed
- **README.md** — version alignment: `v6.0` → `v8.2.0` across all headers and architecture diagram
- **README.md** — clone URL corrected: `github.com/your-org/chimera-gateway` → `github.com/Mr-DS-ML-85/chimera-ai-gateway`
- **README.md** — provider count updated: `21` → `22` in all badges, descriptions, and provider matrix headers
- **README.md** — `15 free providers` references updated to `22 providers` in feature descriptions
- **README.md** — contributing link updated from `arena.ai/c/docs` to correct GitHub repo
- **README.md** — coverage badge updated with Codacy logo and dashboard link
- **README.md** — architecture diagram updated to reference Chimera Gateway v8.2.0
- **README.md** — provider matrix header updated to `v8.2.0 — 22 Providers`
- **README.md** — credits section provider count updated to `22`
- **.env.example** — `GATEWAY_VERSION=8.2.0` is consistent with `__init__.py`

### Fixed
- Clone URL in Quick Start and Contributing sections pointed to non-existent `your-org` placeholder

### Security
- Content Policy re-defined `scan()` functions for correct CSAM/WMD/Self-harm blocking
- WAF hardened against non-ASCII bypass (LDAP Unicode rule) and improved SQLi/CMDi/XSS rules
- SSRF protection: `follow_redirects` disabled globally in `httpx` client
- Admin API CRUD methods restored in `keys/virtual_keys.py`
- Mass Assignment Guard: `role: system` now correctly allowed for legitimate system prompts

---

## [8.1.x] — 2025 (prior minor releases)

> Prior changelog entries will be recorded here as the project matures.

---

## [8.0.0] — 2025-01 — Major Feature Release

### Added
- 16+ new AI providers (Mistral AI, xAI/Grok, DeepSeek, Perplexity, Fireworks AI, DeepInfra, and more)
- Live model auto-discovery system — hourly refresh from each provider's `/models` endpoint
- Dynamic model classification into `reasoning` and `non_reasoning` buckets
- Virtual model routing: `non-reasoning-auto` and `reasoning-auto` aliases
- AES-256-GCM end-to-end encryption (E2EE) for responses
- HMAC request signing for outbound traffic integrity
- Transparency log — append-only SHA-256 audit trail
- Response deduplication via SHA-256 rolling window
- Tool call depth limits (max 3 per response)
- Canary token system for secret/API key exfiltration detection
- Redis-backed nonce registry for replay attack protection
- Custom OpenAI-compatible BYOK endpoint support
- MiniMax provider support

### Changed
- Provider catalogue expanded from 5 to 21+ providers
- Virtual keys system for scoped API key management
- Circuit breaker implementation per provider
- Latency-aware routing (Exponential Moving Average)
- PII redaction in requests and responses

### Security
- AC-1: Payload injection detection (pattern matching + base64 nested scan)
- AC-2: Canary token regex scanner for secret exfiltration
- WAF: SQLi, XSS, CMDi, path traversal, encoded bypass blocking
- Prompt Shield: multi-shot injection, role confusion detection
- SSRF protection: blocks localhost,169.254.x.x, metadata service
- Output Guard: validates tool call structure and response schema
- Content Policy: CSAM, WMD, self-harm blocking

---

## [7.x] — 2024 — Prior Releases

> Legacy versions prior to the v8 major rewrite are not tracked in this changelog.

---

## Upgrade Notes

### v8.0 → v8.2
- No breaking API changes
- MiniMax provider added (if you use MiniMax, add `MINIMAX_API_KEY` to your `.env`)
- Version number is now consistent: `8.2.0` in `__init__.py`, `.env.example`, and README

### Pre-v8.0
- v8.0 was a significant rewrite. The FastAPI app, routing engine, and security layers were redesigned. Review the v7 → v8 migration guide in docs/ before upgrading from pre-8.0 releases.