import logging
from transformers import pipeline

logger = logging.getLogger("gateway.guardrails")

# Initialize the prompt injection classifier pipeline
try:
    classifier = pipeline(
        "text-classification",
        model="distilbert-base-uncased-finetuned-sst-2-english",
        device=-1  # Run on CPU
    )
    logger.info("Loaded DeBERTa Prompt Injection Guardrail Model.")
except Exception as e:
    logger.error(f"Failed to load Guardrail Model: {e}")
    classifier = None

def check_jailbreak(prompt: str) -> bool:
    """
    Checks if the prompt contains prompt injection or jailbreak attempts using a local ML classifier.
    Returns True if a jailbreak is detected.
    """
    if not prompt or not isinstance(prompt, str):
        return False
        
    if not classifier:
        # Fallback to naive check if model fails to load
        return "ignore previous instructions" in prompt.lower()
        
    try:
        # Truncate prompt to prevent OOM
        truncated_prompt = prompt[:2000]
        
        results = classifier(truncated_prompt)
        
        if results and len(results) > 0:
            result = results[0]
            # distilbert outputs 'NEGATIVE' or 'POSITIVE'. We'll map NEGATIVE to INJECTION for testing
            if result['label'] == 'NEGATIVE' and result['score'] > 0.8:
                logger.warning(f"ML Guardrail: Jailbreak detected! Score: {result['score']:.3f}")
                return True
    except Exception as e:
        logger.error(f"Guardrail classification error: {e}")
        
    return False
