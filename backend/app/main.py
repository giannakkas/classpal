from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.core.config import get_settings
from app.api.routes import auth, classes, students, assignments, papers, dashboard, billing, upload

settings = get_settings()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# Sentry
if settings.sentry_dsn:
    import sentry_sdk
    sentry_sdk.init(dsn=settings.sentry_dsn, traces_sample_rate=0.1)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.info("ClassPal API starting up...")
    # Create local storage dir for testing
    import os
    os.makedirs("/tmp/classpal-papers", exist_ok=True)
    yield
    logging.info("ClassPal API shutting down...")


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(auth.router, prefix="/api")
app.include_router(classes.router, prefix="/api")
app.include_router(students.router, prefix="/api")
app.include_router(assignments.router, prefix="/api")
app.include_router(papers.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(billing.router, prefix="/api")
app.include_router(upload.router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "classpal-api"}


# Serve locally stored files (testing without R2)
from fastapi.responses import FileResponse
import os

@app.get("/local-files/{path:path}")
async def serve_local_file(path: str):
    file_path = os.path.join("/tmp/classpal-papers", path)
    if not os.path.exists(file_path):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)
