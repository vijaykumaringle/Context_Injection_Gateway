# Context Injection Gateway (Enterprise Edition)

Context Injection Gateway is an enterprise context orchestration layer that sits between applications and LLMs, dynamically assembling secure, policy-aware, role-specific context before every inference request.

A headless, high-performance reverse proxy middleware designed to intercept outbound LLM API requests and dynamically inject authoritative, role-restricted RAG context from internal databases prior to model inference.

Built with FastAPI, httpx, ChromaDB, BM25, and SQLAlchemy. Features robust Security Interceptors, Advanced RAG, Tiered Rate Limiting, and a premium visual dashboard.

## 🚀 Enterprise Features

- **DLP / PII Masking**: Real-time regex interception engine (`dlp.py`) that redacts sensitive PII (SSNs, Phones, Emails) before they leave your network, seamlessly restoring them in the LLM response.
- **Prompt Guardrails**: Local Hugging Face ML model (`distilbert`) jailbreak classification (`guardrails.py`) that analyzes adversarial inputs instantly and terminates them with `HTTP 403 Forbidden`.
- **Intelligent Model Routing**: Asynchronous routing (`router.py`) with **Auto-Failover Loops**. If a primary route (like `gpt-4`) fails or hits rate limits, the gateway seamlessly falls back to a secondary route (like local `llama3`).
- **Advanced Hybrid RAG**: Merges Semantic Vector Search (ChromaDB) with Exact Keyword Search (BM25) using Reciprocal Rank Fusion (RRF), and then deeply analyzes the context using a **Cross-Encoder Semantic Reranker** for pristine context accuracy.
- **Semantic Caching with TTL**: Bypasses LLM inference for similar queries, now fortified with a 24-hour Time-To-Live (TTL) expiration to prevent serving stale data.
- **Streaming Token Tracking**: Accurately tracks output tokens inside asynchronous streams using `tiktoken` for pristine billing.
- **Tiered Token Quotas**: Deeply integrated rate limiter that monitors total token consumption across `free`, `pro`, and `enterprise` tier allocations.
- **Prometheus Observability**: Automatically exposes a `/metrics` endpoint for Grafana, tracking total token consumption, cache hits, and HTTP latency.
- **Premium Admin Dashboard**: A sleek, dark-mode visual interface to monitor SOC2/HIPAA logs, inject vectors, and manage API Keys.

## 🛠 Setup

1. **Configure Environment**: Create a `.env` file (copied from `.env.template` if available).
   - `OPENAI_API_KEY`: API key for GPT models (Cloud).
   - `OLLAMA_API_BASE`: API base URL for Llama models (Local).
2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Run the Gateway**:
   ```bash
   python main.py
   ```
   *Note: SQLite (`gateway.db`) and ChromaDB (`./vector_store`) will auto-initialize on first run.*

## 📊 Admin Dashboard

Access the visual dashboard at: `http://localhost:8000/admin`

- **Authenticate**: Use a generated Admin JWT to log in.
- **Audit Stream**: Real-time visualization of proxied requests, token counts, and status codes.
- **API Key Management**: Generate tiered API keys (`free`, `pro`, `enterprise`) and revoke them instantly via the UI.
- **Knowledge Base**: Direct UI for injecting new context strings into the hybrid search engine with specific role/topic mappings.

## 🔒 Security & RBAC

### 1. Generating Mock Tokens
Run `python generate_tokens.py` to mint mock JWTs for roles like `admin`, `healthcare_provider`, or `user`. The gateway lazily-syncs these identities into the SQL `users` table upon their first interaction.

### 2. Tiered Rate Limiting
The gateway enforces token-based quotas using the persistent `audit_logs` table in SQLite. It aggregates `input_tokens + output_tokens` consumed over the last hour. If the user exceeds their API Key tier limit, the proxy instantly returns `HTTP 429 Too Many Requests`.

### 3. Identity Resolution
Audit logs securely store an anonymized `user_pseudo_id`. To resolve this to a real user during an investigation:
```bash
python resolve_audit_user.py <HASH>
```

## 📡 Proxied Inference (OpenAI Format)

The gateway intercepts standard `POST /v1/chat/completions` requests.
```bash
curl -X POST "http://localhost:8000/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <TOKEN>" \
  -d '{
    "model": "gpt-4",
    "messages": [{"role": "user", "content": "How do I file the surgical procedure for Patient <SSN>?"}]
  }'
```
Context is injected as `system` instructions. Any SSN is masked by DLP, routed to OpenAI, and securely restored upon return.
