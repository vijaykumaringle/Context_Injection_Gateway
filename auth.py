import os
import logging
from typing import Optional
from fastapi import Request, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from pydantic import BaseModel

logger = logging.getLogger("gateway.auth")

security = HTTPBearer()

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "yoursecretkey_for_testing")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

class User(BaseModel):
    user_id: str
    role: str

async def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)) -> User:
    """Verifies JWT and extracts user/role for RBAC."""
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        role: str = payload.get("role")
        if user_id is None or role is None:
            raise HTTPException(status_code=401, detail="Invalid token payload")
            
        # Lazy sync to database
        try:
            from database import SessionLocal
            from models import APIUser
            db = SessionLocal()
            existing = db.query(APIUser).filter(APIUser.user_id == user_id).first()
            if not existing:
                new_user = APIUser(user_id=user_id, role=role)
                db.add(new_user)
                db.commit()
            db.close()
        except Exception as e:
            logger.error(f"Failed to sync user to database: {e}")
            
        return User(user_id=user_id, role=role)
    except JWTError as e:
        logger.warning(f"Failed JWT validation: {e}")
        raise HTTPException(status_code=401, detail="Could not validate credentials")
