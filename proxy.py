import os
import time
import httpx
from fastapi import Request, Response
from context_injector import inject_context_into_payload
from logger import log_api_request, logger
from auth import User

API_BASE = os.getenv("UPSTREAM_API_BASE", "https://api.openai.com")
API_KEY = os.getenv("UPSTREAM_API_KEY", "")

# Single client instance for connection pooling
http_client = httpx.AsyncClient(base_url=API_BASE)

async def proxy_request(request: Request, user: User, path: str):
    """
    1. Reads incoming request body.
    2. Injects RAG context.
    3. Forwards to upstream API.
    4. Logs the event for SOC2/HIPAA.
    5. Returns streaming response if requested, otherwise normal response.
    """
    start_time = time.time()
    try:
        body = await request.json()
    except Exception:
        body = {}

    # Estimate input tokens rudely or mock it
    # In production, use tiktoken
    input_tokens_estimate = len(str(body)) // 4

    # --- CACHE INTERCEPTION ---
    from semantic_cache import check_semantic_cache, save_to_cache
    
    last_user_msg = ""
    for msg in reversed(body.get("messages", [])):
        if msg.get("role") == "user":
            last_user_msg = msg.get("content", "")
            break
            
    if last_user_msg:
        cached_resp = check_semantic_cache(last_user_msg, role=user.role)
        if cached_resp:
            duration_ms = int((time.time() - start_time) * 1000)
            log_api_request(user.user_id, user.role, path, input_tokens_estimate, len(cached_resp)//4, 200, duration_ms)
            return Response(content=cached_resp, status_code=200, media_type="application/json")

    # --- INJECTION ---
    modified_body = inject_context_into_payload(body, role=user.role)

    # --- FORWARDING ---
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    # Proxy the request
    try:
        upstream_req = http_client.build_request(
            method=request.method,
            url=f"/{path}",
            json=modified_body,
            headers=headers,
            timeout=60.0
        )
        
        # If upstream supports streaming, we should ideally stream back.
        # For simplicity in this baseline, we'll await the full response,
        # but in production we use httpx streaming.
        upstream_resp = await http_client.send(upstream_req)
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        if upstream_resp.status_code == 200 and last_user_msg:
            # We save the raw string back to the cache
            try:
                save_to_cache(last_user_msg, user.role, upstream_resp.text)
            except Exception as e:
                logger.error(f"Error saving successful response to cache: {e}")

        # Log the compliant record
        log_api_request(
            user_id=user.user_id,
            role=user.role,
            path=path,
            input_tokens=input_tokens_estimate,
            output_tokens=len(upstream_resp.text) // 4, # rough mock
            status_code=upstream_resp.status_code,
            duration_ms=duration_ms
        )
        
        return Response(
            content=upstream_resp.content,
            status_code=upstream_resp.status_code,
            media_type=upstream_resp.headers.get("Content-Type", "application/json")
        )

    except Exception as e:
        logger.error(f"Upstream proxy failed: {e}")
        duration_ms = int((time.time() - start_time) * 1000)
        log_api_request(user.user_id, user.role, path, input_tokens_estimate, 0, 500, duration_ms)
        return Response(content='{"error": "Upstream error"}', status_code=502, media_type="application/json")
