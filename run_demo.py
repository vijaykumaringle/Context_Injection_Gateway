import os
import requests
from generate_tokens import create_token
import time

# Create tokens
admin_token = create_token("admin_999", "admin")
doc_token = create_token("doctor_007", "healthcare_provider")

headers_admin = {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}
headers_doc = {"Authorization": f"Bearer {doc_token}", "Content-Type": "application/json"}

print("== 1. Seeding Vector Store via Admin API ==")
# Injecting a document into persistent ChromaDB
doc_payload = {
    "document": "Surgical procedures must be filed under the new code system ABC-2026. Only authorized surgeons can view.",
    "role": "healthcare_provider",
    "topic": "procedures",
    "doc_id": "doc_surgery_1"
}
resp = requests.post("http://localhost:8000/api/documents", json=doc_payload, headers=headers_admin)
print(f"Status: {resp.status_code}, Response: {resp.text}\n")

print("== 2. Sending LLM proxy request (will use local Ollama) ==")
llm_payload = {
    "model": "llama3",
    "messages": [{"role": "user", "content": "How do I file the surgical procedure I did today?"}]
}
# Using the doctor token so it queries the 'healthcare_provider' role documents!
proxy_resp = requests.post("http://localhost:8000/v1/chat/completions", json=llm_payload, headers=headers_doc)
print(f"Proxy LLM Access Status Code: {proxy_resp.status_code}")
# Print first 200 chars of response
print(f"Proxy Response: {proxy_resp.text[:200]}...\n")

time.sleep(1) # wait for log

print("== 3. Fetching updated SOC2/HIPAA Logs from SQLite DB ==")
log_resp = requests.get("http://localhost:8000/api/logs", headers=headers_admin)
print(f"Log Output (JSON):\n{log_resp.text}\n")
