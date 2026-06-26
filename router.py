import os
import logging

logger = logging.getLogger("gateway.router")

# Map models to their respective upstream API bases and fallback models
ROUTING_TABLE = {
    "llama": {
        "primary": ("http://localhost:11434", "OLLAMA_API_KEY"),
        "fallbacks": [] # If local fails, no cloud fallback configured by default for privacy
    },
    "gpt": {
        "primary": ("https://api.openai.com", "OPENAI_API_KEY"),
        "fallbacks": [
            ("http://localhost:11434", "OLLAMA_API_KEY") # Fallback to local llama3 if GPT fails
        ]
    },
    "claude": {
        "primary": ("https://api.anthropic.com", "ANTHROPIC_API_KEY"),
        "fallbacks": [
            ("https://api.openai.com", "OPENAI_API_KEY"), # Fallback to OpenAI
            ("http://localhost:11434", "OLLAMA_API_KEY")  # Then fallback to local
        ]
    }
}

DEFAULT_API_BASE = os.getenv("UPSTREAM_API_BASE", "https://api.openai.com")
DEFAULT_API_KEY = os.getenv("UPSTREAM_API_KEY", "")

def route_model(model_name: str) -> tuple[tuple[str, str], list[tuple[str, str]]]:
    """
    Determines the correct API base and key for the given model.
    Returns:
        primary_route: (api_base, api_key)
        fallback_routes: [ (api_base, api_key), ... ]
    """
    if not model_name:
        return (DEFAULT_API_BASE, DEFAULT_API_KEY), []
        
    lower_model = model_name.lower()
    for prefix, routing_info in ROUTING_TABLE.items():
        if lower_model.startswith(prefix):
            primary_base, env_var = routing_info["primary"]
            primary_key = os.getenv(env_var, DEFAULT_API_KEY)
            
            fallbacks = []
            for f_base, f_env_var in routing_info.get("fallbacks", []):
                fallbacks.append((f_base, os.getenv(f_env_var, DEFAULT_API_KEY)))
                
            logger.debug(f"Routing model '{model_name}' to {primary_base} with {len(fallbacks)} fallbacks.")
            return (primary_base, primary_key), fallbacks
            
    # Fallback to default
    logger.debug(f"No specific route found for '{model_name}', using default.")
    return (DEFAULT_API_BASE, DEFAULT_API_KEY), []
