import os
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Depends, Request, Response, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from auth import verify_token, User
from proxy import proxy_request
from logger import logger

from database import engine, Base, get_db
import models
from sqlalchemy.orm import Session
from rag_engine import add_document_to_kb, get_all_documents

# Ensure tables are created
models.Base.metadata.create_all(bind=engine)

from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI(title="Context Injection Gateway")

# Expose Prometheus /metrics endpoint
Instrumentator().instrument(app).expose(app)

# Mount Static Files for the Dashboard
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/admin", response_class=FileResponse)
async def admin_dashboard():
    return "static/index.html"

@app.on_event("startup")
async def startup_event():
    logger.info("Gateway started. Ready to intercept LLM API requests.")

class DocumentPayload(BaseModel):
    document: str
    role: str
    topic: str
    doc_id: str

@app.post("/api/documents")
async def add_document(payload: DocumentPayload, user: User = Depends(verify_token)):
    if user.role != "admin":
        return Response(status_code=403, content="Admins only")
    
    await add_document_to_kb(payload.doc_id, payload.document, payload.role, payload.topic)
    return {"status": "success", "doc_id": payload.doc_id}

@app.get("/api/documents")
async def list_documents(user: User = Depends(verify_token)):
    if user.role != "admin":
        return Response(status_code=403, content="Admins only")
    
    docs = await get_all_documents()
    return docs

@app.get("/api/logs")
async def get_logs(db: Session = Depends(get_db), user: User = Depends(verify_token)):
    if user.role != "admin":
        return Response(status_code=403, content="Admins only")
    logs = db.query(models.AuditLog).order_by(models.AuditLog.timestamp.desc()).limit(50).all()
    return logs

@app.get("/api/users")
async def get_users(db: Session = Depends(get_db), user: User = Depends(verify_token)):
    if user.role != "admin":
        return Response(status_code=403, content="Admins only")
    users = db.query(models.APIUser).order_by(models.APIUser.created_at.desc()).limit(50).all()
    return users

import hashlib
import secrets

class ApiKeyPayload(BaseModel):
    user_id: str
    tier: str

@app.get("/api/keys")
async def get_keys(db: Session = Depends(get_db), user: User = Depends(verify_token)):
    if user.role != "admin":
        return Response(status_code=403, content="Admins only")
    keys = db.query(models.ApiKey).order_by(models.ApiKey.created_at.desc()).all()
    return keys

@app.post("/api/keys")
async def create_key(payload: ApiKeyPayload, db: Session = Depends(get_db), user: User = Depends(verify_token)):
    if user.role != "admin":
        return Response(status_code=403, content="Admins only")
    
    # Generate a dummy key format for demonstration
    raw_key = f"sk-{secrets.token_urlsafe(16)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    prefix = raw_key[:7]
    
    new_key = models.ApiKey(
        key_hash=key_hash,
        prefix=prefix,
        user_id=payload.user_id,
        tier=payload.tier
    )
    db.add(new_key)
    db.commit()
    
    return {"raw_key": raw_key, "user_id": payload.user_id, "tier": payload.tier}

@app.delete("/api/keys/{key_id}")
async def revoke_key(key_id: int, db: Session = Depends(get_db), user: User = Depends(verify_token)):
    if user.role != "admin":
        return Response(status_code=403, content="Admins only")
        
    key = db.query(models.ApiKey).filter(models.ApiKey.id == key_id).first()
    if key:
        key.is_revoked = True
        db.commit()
    return {"status": "revoked"}

from ratelimiter import check_rate_limit

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def catch_all_proxy(request: Request, path: str, background_tasks: BackgroundTasks, user: User = Depends(check_rate_limit)):
    """
    Catch-all route that handles any request sent to the gateway.
    Typically clients will send POST /v1/chat/completions to this gateway instead of api.openai.com.
    """
    logger.debug(f"Intercepted request for /{path} by user {user.user_id}")
    return await proxy_request(request, user, path, background_tasks)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("GATEWAY_PORT", 8000))
    host = os.getenv("GATEWAY_HOST", "0.0.0.0")
    uvicorn.run("main:app", host=host, port=port, reload=True)
