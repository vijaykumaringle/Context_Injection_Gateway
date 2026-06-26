import os
import time
import httpx
from fastapi import Request, Response, BackgroundTasks
from fastapi.responses import StreamingResponse
from context_injector import inject_context_into_payload
from logger import log_api_request, logger
from auth import User
from semantic_cache import check_semantic_cache, save_to_cache
from dlp import PIIInterceptor
from guardrails import check_jailbreak
from router import route_model

# Single client instance for connection pooling without fixed base url
http_client = httpx.AsyncClient()

async def proxy_request(request: Request, user: User, path: str, background_tasks: BackgroundTasks):
    start_time = time.time()
    try:
        body = await request.json()
    except Exception:
        body = {}

    model_name = body.get("model", "")
    api_base, api_key = route_model(model_name)

    input_tokens_estimate = len(str(body)) // 4

    # --- SECURITY: DLP REDACTION ---
    dlp = PIIInterceptor()
    for msg in body.get("messages", []):
        if "content" in msg and isinstance(msg["content"], str):
            msg["content"] = dlp.redact(msg["content"])

    # Extract user message for RAG and Guardrails
    last_user_msg = ""
    for msg in reversed(body.get("messages", [])):
        if msg.get("role") == "user":
            last_user_msg = msg.get("content", "")
            break
            
    # --- SECURITY: JAILBREAK DETECTION ---
    if check_jailbreak(last_user_msg):
        duration_ms = int((time.time() - start_time) * 1000)
        background_tasks.add_task(log_api_request, user.user_id, user.role, path, input_tokens_estimate, 0, 403, duration_ms)
        return Response(content='{"error": "Forbidden - Jailbreak or Policy Violation Detected"}', status_code=403, media_type="application/json")

    # --- CACHE INTERCEPTION ---
    if last_user_msg:
        cached_resp = await check_semantic_cache(last_user_msg, role=user.role)
        if cached_resp:
            # Restore PII before returning from cache
            restored_cache = dlp.restore(cached_resp)
            duration_ms = int((time.time() - start_time) * 1000)
            background_tasks.add_task(log_api_request, user.user_id, user.role, path, input_tokens_estimate, len(restored_cache)//4, 200, duration_ms)
            return Response(content=restored_cache, status_code=200, media_type="application/json")

    # --- INJECTION ---
    modified_body = await inject_context_into_payload(body, role=user.role)

    # --- FORWARDING ---
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    is_stream = modified_body.get("stream", False)
    
    try:
        if is_stream:
            async def stream_generator():
                async with http_client.stream(request.method, f"{api_base}/{path}", json=modified_body, headers=headers) as upstream_resp:
                    async for chunk in upstream_resp.aiter_bytes():
                        # Restore PII in chunk
                        try:
                            decoded = chunk.decode("utf-8")
                            restored = dlp.restore(decoded)
                            yield restored.encode("utf-8")
                        except UnicodeDecodeError:
                            yield chunk
                            
                duration_ms = int((time.time() - start_time) * 1000)
                background_tasks.add_task(log_api_request, user.user_id, user.role, path, input_tokens_estimate, 0, 200, duration_ms)
            return StreamingResponse(stream_generator(), media_type="text/event-stream")
        else:
            upstream_req = http_client.build_request(
                method=request.method,
                url=f"{api_base}/{path}",
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
                
                # Restore PII
                restored_text = dlp.restore(upstream_resp.text)
                
                if last_user_msg:
                    # Save the restored text to cache
                    background_tasks.add_task(save_to_cache, last_user_msg, user.role, restored_text)

            else:
                restored_text = upstream_resp.text

            background_tasks.add_task(log_api_request, user.user_id, user.role, path, input_tokens_estimate, output_tokens, upstream_resp.status_code, duration_ms)
            
            return Response(
                content=restored_text.encode("utf-8"),
                status_code=upstream_resp.status_code,
                media_type=upstream_resp.headers.get("Content-Type", "application/json")
            )

    except Exception as e:
        logger.error(f"Upstream proxy failed: {e}")
        duration_ms = int((time.time() - start_time) * 1000)
        background_tasks.add_task(log_api_request, user.user_id, user.role, path, input_tokens_estimate, 0, 502, duration_ms)
        return Response(content='{"error": "Upstream error"}', status_code=502, media_type="application/json")
