import os
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Depends, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from auth import verify_token, User
from proxy import proxy_request
from logger import logger

from database import engine, Base, get_db
import models
from sqlalchemy.orm import Session
from rag_engine import collection

# Ensure tables are created
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Context Injection Gateway")

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
    
    collection.add(
        documents=[payload.document],
        metadatas=[{"role": payload.role, "topic": payload.topic}],
        ids=[payload.doc_id]
    )
    return {"status": "success", "doc_id": payload.doc_id}

@app.get("/api/logs")
async def get_logs(db: Session = Depends(get_db), user: User = Depends(verify_token)):
    if user.role != "admin":
        return Response(status_code=403, content="Admins only")
    logs = db.query(models.AuditLog).order_by(models.AuditLog.timestamp.desc()).limit(50).all()
    return logs

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def catch_all_proxy(request: Request, path: str, user: User = Depends(verify_token)):
    """
    Catch-all route that handles any request sent to the gateway.
    Typically clients will send POST /v1/chat/completions to this gateway instead of api.openai.com.
    """
    logger.debug(f"Intercepted request for /{path} by user {user.user_id}")
    return await proxy_request(request, user, path)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("GATEWAY_PORT", 8000))
    host = os.getenv("GATEWAY_HOST", "0.0.0.0")
    uvicorn.run("main:app", host=host, port=port, reload=True)
