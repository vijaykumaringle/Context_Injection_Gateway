# Context Injection Gateway

A headless reverse proxy middleware designed to intercept outbound LLM API requests and dynamically inject authoritative, role-restricted RAG context from internal databases prior to model inference.

Built with FastAPI, httpx, ChromaDB, and SQLAlchemy. Features SOC2/HIPAA compliance logging, semantic caching, rate limiting, and a premium visual dashboard.

## 🚀 Key Features

- **Dynamic RAG Injection**: Automatically appends role-restricted context to prompts based on vector similarity.
- **Semantic Caching**: Bypasses LLM inference for similar queries using an internal ChromaDB cache, reducing latency and costs.
- **Rate Limiting**: Enforces usage quotas (e.g., 100 req/hr) based on persistent SQLite audit logs to prevent infrastructure abuse.
- **Compliance Logging**: SOC2/HIPAA compliant logging with anonymized user identity hashes and strict PII exclusion.
- **Premium Admin Dashboard**: A sleek, dark-mode visual interface to monitor logs and manage knowledge base vectors.

## 🛠 Setup

1. **Configure Environment**: Create a `.env` file (copied from `.env.template` if available).
   - `UPSTREAM_API_BASE`: Defaults to `http://localhost:11434` (Ollama).
   - `UPSTREAM_API_KEY`: Your provider API key (or `ollama` for local).
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
- **Knowledge Base**: Direct UI for injecting new context strings into the vector store with specific role/topic mappings.

## 🔒 Security & RBAC

### 1. Generating Mock Tokens
Run `python generate_tokens.py` to mint mock JWTs for roles like `admin`, `healthcare_provider`, or `user`. The gateway lazily-syncs these identities into the SQL `users` table upon their first interaction.

### 2. Rate Limiting
The gateway enforces a quota of **100 requests per hour** per user. It checks the persistent `audit_logs` table in SQLite before processing any proxied request. If the limit is reached, it returns an `HTTP 429 Too Many Requests`.

### 3. Identity Resolution
Audit logs store an anonymized `user_pseudo_id`. To resolve this to a real user during an investigation:
```bash
python resolve_audit_user.py <HASH>
```

## 🧠 Semantic Caching

The gateway maintains a semantic cache in ChromaDB.
- **Logic**: If an incoming prompt has a vector distance `< 0.5` to a previously cached prompt (within the same role), the gateway returns the cached response instantly (~50ms latency).
- **Benefit**: Drastically reduces LLM compute costs and local GPU usage.

## 📡 Proxied Inference (OpenAI Format)

The gateway intercepts standard `POST /v1/chat/completions` requests.
```bash
curl -X POST "http://localhost:8000/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <TOKEN>" \
  -d '{
    "model": "llama3",
    "messages": [{"role": "user", "content": "How do I file the surgical procedure?"}]
  }'
```
Context is injected as `system` instructions before being forwarded to the upstream local or cloud LLM.
