from sqlalchemy import Column, Integer, String, DateTime, Index, Boolean
from datetime import datetime
from database import Base

class APIUser(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, unique=True, index=True, nullable=False)
    user_pseudo_id = Column(String, unique=True, index=True, nullable=False)
    role = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index('idx_user_time', 'user_pseudo_id', 'timestamp'),
    )

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    user_pseudo_id = Column(String, index=True, nullable=False)
    role = Column(String, nullable=False)
    path = Column(String, nullable=False)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    status_code = Column(Integer, nullable=False)
    duration_ms = Column(Integer, nullable=False)

class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    key_hash = Column(String, unique=True, index=True, nullable=False)
    prefix = Column(String, nullable=False)
    user_id = Column(String, nullable=False)
    tier = Column(String, default="free")
    is_revoked = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
