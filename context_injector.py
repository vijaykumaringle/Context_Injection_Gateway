import logging
from rag_engine import retrieve_context_for_role

logger = logging.getLogger("gateway.injector")

def inject_context_into_payload(payload: dict, role: str) -> dict:
    """
    Takes an OpenAI-style payload, extracts the last user message to query context,
    and prepends/appends the retrieved RAG context as a system prompt.
    """
    messages = payload.get("messages", [])
    if not messages:
        return payload
        
    # Extract the last user message to use as the query
    last_user_msg = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            last_user_msg = msg.get("content", "")
            if isinstance(last_user_msg, list):
                # Handle gpt-4-vision format (list of dicts)
                texts = [item.get("text", "") for item in last_user_msg if item.get("type") == "text"]
                last_user_msg = " ".join(texts)
            break
            
    if not last_user_msg:
        logger.debug("No user message found to use for context query.")
        return payload
        
    # Retrieve context
    context = retrieve_context_for_role(last_user_msg, role=role)
    
    if context:
        logger.debug(f"Injecting retrieved context length: {len(context)}")
        injection_text = f"INTERNAL KNOWLEDGE BASE CONTEXT (Role restricted to {role}):\n{context}\n\nUse this context to inform your answer."
        
        # Look for existing system message to modify, or prepend a new one
        system_found = False
        for msg in messages:
            if msg.get("role") == "system":
                msg["content"] = str(msg.get("content", "")) + "\n\n" + injection_text
                system_found = True
                break
                
        if not system_found:
            messages.insert(0, {"role": "system", "content": injection_text})
            
    return payload
