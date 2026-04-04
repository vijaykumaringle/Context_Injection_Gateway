import logging
import json
import hashlib
from datetime import datetime

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger_name": record.name,
            "message": record.getMessage(),
        }
        
        # Merge any extra metadata (e.g. from structured logs)
        if hasattr(record, "extra_info"):
            log_data.update(record.extra_info)
            
        return json.dumps(log_data)

def setup_logger():
    logger = logging.getLogger("gateway")
    logger.setLevel(logging.INFO)
    
    # Prevent duplicated logs if setup multiple times
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        
    return logger

logger = setup_logger()

def log_api_request(user_id: str, role: str, path: str, input_tokens: int = 0, output_tokens: int = 0, status_code: int = 200, duration_ms: int = 0):
    """
    HIPAA/SOC2 compliant logging.
    We hash the user_id if needed, but here we assume internal IDs which are pseudo-anonymous.
    We carefully DO NOT log the prompt or response body.
    """
    hashed_user = hashlib.sha256(user_id.encode()).hexdigest()[:16]
    extra_info = {
        "event": "llm_api_call",
        "user_pseudo_id": hashed_user,
        "role": role,
        "path": path,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "status_code": status_code,
        "duration_ms": duration_ms
    }
    
    logger.info("Outbound LLM API Request", extra={"extra_info": extra_info})

    # Save to Relational DB
    try:
        from database import SessionLocal
        from models import AuditLog
        
        db = SessionLocal()
        audit_log = AuditLog(
            user_pseudo_id=hashed_user,
            role=role,
            path=path,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            status_code=status_code,
            duration_ms=duration_ms
        )
        db.add(audit_log)
        db.commit()
        db.close()
    except Exception as e:
        logger.error(f"Failed to write audit log to database: {e}")
