import os
import time
import httpx
from fastapi import Request, Response, BackgroundTasks
from fastapi.responses import StreamingResponse
from context_injector import inject_context_into_payload
from logger import log_api_request, logger
from auth import User

API_BASE = os.getenv("UPSTREAM_API_BASE", "https://api.openai.com")
API_KEY = os.getenv("UPSTREAM_API_KEY", "")

# Single client instance for connection pooling
http_client = httpx.AsyncClient(base_url=API_BASE)

async def proxy_request(request: Request, user: User, path: str, background_tasks: BackgroundTasks):
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
        cached_resp = await check_semantic_cache(last_user_msg, role=user.role)
        if cached_resp:
            duration_ms = int((time.time() - start_time) * 1000)
            background_tasks.add_task(log_api_request, user.user_id, user.role, path, input_tokens_estimate, len(cached_resp)//4, 200, duration_ms)
            return Response(content=cached_resp, status_code=200, media_type="application/json")

    # --- INJECTION ---
    modified_body = await inject_context_into_payload(body, role=user.role)

    # --- FORWARDING ---
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    # Proxy the request
    is_stream = modified_body.get("stream", False)
    
    try:
        if is_stream:
            async def stream_generator():
                async with http_client.stream(request.method, f"{API_BASE}/{path}", json=modified_body, headers=headers) as upstream_resp:
                    async for chunk in upstream_resp.aiter_bytes():
                        yield chunk
                duration_ms = int((time.time() - start_time) * 1000)
                # Cache skip for streams in this baseline, but we do log it
                background_tasks.add_task(log_api_request, user.user_id, user.role, path, input_tokens_estimate, 0, 200, duration_ms)
            return StreamingResponse(stream_generator(), media_type="text/event-stream")
        else:
            upstream_req = http_client.build_request(
                method=request.method,
                url=f"/{path}",
                json=modified_body,
                headers=headers,
                timeout=60.0
            )
            upstream_resp = await http_client.send(upstream_req)
            duration_ms = int((time.time() - start_time) * 1000)
            
            output_tokens = 0
            if upstream_resp.status_code == 200:
                try:
                    resp_json = upstream_resp.json()
                    if "usage" in resp_json:
                        input_tokens_estimate = resp_json["usage"].get("prompt_tokens", input_tokens_estimate)
                        output_tokens = resp_json["usage"].get("completion_tokens", output_tokens)
                except Exception:
                    output_tokens = len(upstream_resp.text) // 4
                
                if last_user_msg:
                    background_tasks.add_task(save_to_cache, last_user_msg, user.role, upstream_resp.text)

            background_tasks.add_task(log_api_request, user.user_id, user.role, path, input_tokens_estimate, output_tokens, upstream_resp.status_code, duration_ms)
            
            return Response(
                content=upstream_resp.content,
                status_code=upstream_resp.status_code,
                media_type=upstream_resp.headers.get("Content-Type", "application/json")
            )

    except Exception as e:
        logger.error(f"Upstream proxy failed: {e}")
        duration_ms = int((time.time() - start_time) * 1000)
        background_tasks.add_task(log_api_request, user.user_id, user.role, path, input_tokens_estimate, 0, 502, duration_ms)
        return Response(content='{"error": "Upstream error"}', status_code=502, media_type="application/json")
