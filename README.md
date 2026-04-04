# Context Injection Gateway

A headless reverse proxy middleware designed to intercept outbound LLM API requests and dynamically inject authoritative, role-restricted RAG context from internal databases prior to model inference. 

Built with FastAPI, httpx, ChromaDB, and SQLAlchemy. Features SOC2/HIPAA compliance logging mechanisms and JWT-based Role-Based Access Control (RBAC).

## Setup
1. Define your upstream API logic in `.env` (Defaults to local Ollama logic via `http://localhost:11434`).
2. Install dependencies: `pip install -r requirements.txt`
3. Run the gateway: `python main.py` or `uvicorn main:app --reload`
*Note: Our SQLite database (`gateway.db`) and vector database (`./vector_store`) will dynamically auto-generate themselves upon runtime without the need for external containers!*

## Persistent Databases

The gateway relies on two native data layers:
1. **ChromaDB (`/vector_store`)**: A persistent vector database that stores all authoritative knowledge context for RAG injection.
2. **SQLite via SQLAlchemy (`gateway.db`)**: A relational structure that holds the `users` dimension table and the SOC2 compliant `audit_logs` ledger.

## Gateway Core Usage

### 1. Generating Mock Tokens
Run `python generate_tokens.py` to mint mock JWTs assigned to specific roles (like `admin` or `healthcare_provider`). When an unknown token interacts with the gateway for the first time, its identity is lazily-synced into the SQL `users` table seamlessly securely sealing the identity.

### 2. Admin Capabilities: Context & Logs
With an admin token, you can directly interact with the management endpoints:
- **`POST /api/documents`**: Empowers admins to seed new knowledge directly into the Persistent ChromaDB layer. Requires `document`, `role`, `topic`, and `doc_id` inside the payload.
- **`GET /api/logs`**: Visualizes the latest 50 compliant audit traces from the SQL db.

### 3. Proxied Inference (OpenAI Format)
The proxy intercepts the raw `POST /v1/chat/completions` pathway.
```bash
curl -X POST "http://localhost:8000/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <MOCK_ROLE_TOKEN>" \
  -d '{
    "model": "llama3",
    "messages": [{"role": "user", "content": "How do I file the surgical procedure?"}]
  }'
```
Upon interception, the gateway runs the last `user` message against the vector `role` logic. Matches are strategically appended as `system` instructions prior to the forward.

## Secure Identity Resolution (`resolve_audit_user.py`)

For adherence to HIPAA compliance, the SQL `audit_logs` securely convert plaintext User IDs into salted hashes (`user_pseudo_id`) prior to committing the trace, effectively prohibiting unauthorized identity leaks on dashboard analytics.

However, incident response administrators retain the capability to resolve suspicious payloads backwards utilizing the internal tool:
```bash
python resolve_audit_user.py <user_pseudo_id>
```
The script internally queries the mapped SQLite database recursively processing identity hashes until a confident forward-computed match identifies the explicit culprit.
