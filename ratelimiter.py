import logging
import hashlib
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status, Depends
from sqlalchemy import func
from database import SessionLocal
from models import AuditLog, ApiKey
from auth import verify_token, User
from fastapi.concurrency import run_in_threadpool

logger = logging.getLogger("gateway.ratelimit")

TIER_LIMITS = {
    "free": 1000,
    "pro": 10000,
    "enterprise": 100000
}

def check_rate_limit_sync(hashed_user: str, user_id: str) -> tuple[int, int]:
    db = SessionLocal()
    
    # 1. Determine Tier
    key_record = db.query(ApiKey).filter(
        ApiKey.user_id == user_id,
        ApiKey.is_revoked.is_(False)
    ).first()
    
    tier = key_record.tier if key_record else "free"
    token_limit = TIER_LIMITS.get(tier, TIER_LIMITS["free"])
    
    # 2. Calculate Token Usage in last hour
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    
    usage = db.query(
        func.sum(AuditLog.input_tokens + AuditLog.output_tokens)
    ).filter(
        AuditLog.user_pseudo_id == hashed_user,
        AuditLog.timestamp >= one_hour_ago
    ).scalar()
    
    db.close()
    
    total_tokens = usage or 0
    return total_tokens, token_limit

async def check_rate_limit(user: User = Depends(verify_token)) -> User:
    """
    Middleware dependency to enforce tiered token usage quotas.
    Queries the SQLite AuditLog asynchronously.
    """
    hashed_user = hashlib.sha256(user.user_id.encode()).hexdigest()[:16]
    
    try:
        total_tokens, token_limit = await run_in_threadpool(check_rate_limit_sync, hashed_user, user.user_id)
        
        if total_tokens >= token_limit:
            logger.warning(f"Rate limit breached by {hashed_user}. (Tokens: {total_tokens}/{token_limit})")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. You have used {total_tokens} tokens in the last hour. Tier limit is {token_limit}."
            )
            
        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Rate limiting failure: {e}")
        # Fail open typically preferred in enterprise gateways unless strictly enforced
        return user
