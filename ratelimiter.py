import logging
import hashlib
from datetime import datetime, timedelta
from fastapi import HTTPException, status, Depends
from database import SessionLocal
from models import AuditLog
from auth import verify_token, User

logger = logging.getLogger("gateway.ratelimit")

# Max requests allowed per hour per user
RATE_LIMIT_QUOTA = 100

from fastapi.concurrency import run_in_threadpool

def check_rate_limit_sync(hashed_user: str) -> int:
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    db = SessionLocal()
    request_count = db.query(AuditLog).filter(
        AuditLog.user_pseudo_id == hashed_user,
        AuditLog.timestamp >= one_hour_ago
    ).count()
    db.close()
    return request_count

async def check_rate_limit(user: User = Depends(verify_token)) -> User:
    """
    Middleware dependency to enforce usage quotas.
    Queries the SQLite AuditLog asynchronously.
    """
    hashed_user = hashlib.sha256(user.user_id.encode()).hexdigest()[:16]
    
    try:
        request_count = await run_in_threadpool(check_rate_limit_sync, hashed_user)
        
        if request_count >= RATE_LIMIT_QUOTA:
            logger.warning(f"Rate limit breached by {hashed_user}. (Count: {request_count})")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. You have made {request_count} requests in the last hour. Limit is {RATE_LIMIT_QUOTA}."
            )
            
        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Rate limiting failure: {e}")
        # Fail open typically preferred in enterprise gateways unless strictly enforced
        return user
