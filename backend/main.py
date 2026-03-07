"""backend/main.py
Enterprise backend entrypoint preserving existing API compatibility.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.router import router as backend_router
from core.config import settings


app = FastAPI(
    title="ACAP Enterprise Backend",
    version="1.0.0",
    docs_url="/backend/docs",
    openapi_url="/backend/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
)

app.include_router(backend_router)
