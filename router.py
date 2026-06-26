import os
import logging

logger = logging.getLogger("gateway.router")

# Map models to their respective upstream API bases and optionally a different API key
ROUTING_TABLE = {
    "llama": ("http://localhost:11434", "OLLAMA_API_KEY"),
    "gpt": ("https://api.openai.com", "OPENAI_API_KEY"),
    "claude": ("https://api.anthropic.com", "ANTHROPIC_API_KEY")
}

DEFAULT_API_BASE = os.getenv("UPSTREAM_API_BASE", "https://api.openai.com")
DEFAULT_API_KEY = os.getenv("UPSTREAM_API_KEY", "")

def route_model(model_name: str) -> tuple[str, str]:
    """
    Determines the correct API base and key for the given model.
    """
    if not model_name:
        return DEFAULT_API_BASE, DEFAULT_API_KEY
        
    lower_model = model_name.lower()
    for prefix, (api_base, env_var) in ROUTING_TABLE.items():
        if lower_model.startswith(prefix):
            api_key = os.getenv(env_var, DEFAULT_API_KEY)
            logger.debug(f"Routing model '{model_name}' to {api_base}")
            return api_base, api_key
            
    # Fallback to default
    logger.debug(f"No specific route found for '{model_name}', using default.")
    return DEFAULT_API_BASE, DEFAULT_API_KEY
