import uuid
import logging
import time
from fastapi.concurrency import run_in_threadpool
from rag_engine import chroma_client

logger = logging.getLogger("gateway.cache")

# Retrieve or create an isolated collection for semantic query caching
cache_collection = chroma_client.get_or_create_collection(name="semantic_cache")

# The maximum distance required to constitute a "semantic hit"
# Lower number requires higher exactness (Default l2 distance used)
CACHE_THRESHOLD = 0.5

def _query_cache_sync(prompt: str, role: str):
    return cache_collection.query(
        query_texts=[prompt],
        n_results=1,
        where={"role": role} 
    )

async def check_semantic_cache(prompt: str, role: str) -> str:
    """
    Checks if a highly similar prompt has been asked previously by this role asynchronously.
    """
    try:
        results = await run_in_threadpool(_query_cache_sync, prompt, role)
        
        # Guard against empty cache or totally mismatched results
        if not results or not results.get("distances") or not len(results["distances"][0]):
            return None
            
        distance = results["distances"][0][0]
        
        if distance < CACHE_THRESHOLD:
            meta = results["metadatas"][0][0]
            timestamp = meta.get("timestamp", 0)
            
            # Check 24 hour TTL
            if time.time() - float(timestamp) > 86400:
                logger.info("Semantic cache expired (TTL). Purging.")
                def _del():
                    cache_collection.delete(ids=[results["ids"][0][0]])
                await run_in_threadpool(_del)
                return None
                
            logger.info(f"SEMANTIC CACHE HIT! Distance: {distance:.3f} | Bypassing LLM.")
            # Response is securely stored in the metadata since the document itself is the embedded prompt
            cached_response = meta["response"]
            return cached_response
            
        logger.debug(f"Semantic Cache Miss. Closest distance: {distance:.3f} (Requires < {CACHE_THRESHOLD})")
        return None
        
    except Exception as e:
        logger.error(f"Semantic cache retrieval failed: {e}")
        return None

def _add_cache_sync(prompt: str, role: str, response: str, doc_id: str):
    cache_collection.add(
        documents=[prompt],
        metadatas=[{"role": role, "response": response, "timestamp": time.time()}],
        ids=[doc_id]
    )

async def save_to_cache(prompt: str, role: str, response: str):
    """
    Securely saves a successful LLM output into the vector base for future caching.
    """
    try:
        doc_id = str(uuid.uuid4())
        await run_in_threadpool(_add_cache_sync, prompt, role, response, doc_id)
        logger.debug(f"Saved inference output to semantic cache ID: {doc_id}")
    except Exception as e:
        logger.error(f"Failed to write to semantic cache: {e}")
