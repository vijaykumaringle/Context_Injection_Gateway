import uuid
import logging
from rag_engine import chroma_client

logger = logging.getLogger("gateway.cache")

# Retrieve or create an isolated collection for semantic query caching
cache_collection = chroma_client.get_or_create_collection(name="semantic_cache")

# The maximum distance required to constitute a "semantic hit"
# Lower number requires higher exactness (Default l2 distance used)
CACHE_THRESHOLD = 0.5

def check_semantic_cache(prompt: str, role: str) -> str:
    """
    Checks if a highly similar prompt has been asked previously by this role.
    If yes, returns the cached textual response to completely bypass the LLM.
    """
    try:
        results = cache_collection.query(
            query_texts=[prompt],
            n_results=1,
            where={"role": role} 
        )
        
        # Guard against empty cache or totally mismatched results
        if not results or not results.get("distances") or not len(results["distances"][0]):
            return None
            
        distance = results["distances"][0][0]
        
        if distance < CACHE_THRESHOLD:
            logger.info(f"SEMANTIC CACHE HIT! Distance: {distance:.3f} | Bypassing LLM.")
            # Response is securely stored in the metadata since the document itself is the embedded prompt
            cached_response = results["metadatas"][0][0]["response"]
            return cached_response
            
        logger.debug(f"Semantic Cache Miss. Closest distance: {distance:.3f} (Requires < {CACHE_THRESHOLD})")
        return None
        
    except Exception as e:
        logger.error(f"Semantic cache retrieval failed: {e}")
        return None

def save_to_cache(prompt: str, role: str, response: str):
    """
    Securely saves a successful LLM output into the vector base for future caching.
    """
    try:
        doc_id = str(uuid.uuid4())
        cache_collection.add(
            documents=[prompt], # Embed the prompt so future prompts match against it!
            metadatas=[{"role": role, "response": response}], # Store the actual output safely in metadata
            ids=[doc_id]
        )
        logger.debug(f"Saved inference output to semantic cache ID: {doc_id}")
    except Exception as e:
        logger.error(f"Failed to write to semantic cache: {e}")
