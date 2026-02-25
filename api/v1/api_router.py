"""api/v1/api_router.py — all routers registered"""
from fastapi import APIRouter
from api.v1.endpoints import audit, auth, health, engagement, grc, engine

api_router = APIRouter()
api_router.include_router(auth.router,       prefix="/auth",       tags=["Auth"])
api_router.include_router(audit.router,      prefix="/audit",      tags=["Evidence Vault"])
api_router.include_router(engagement.router, prefix="/engagement", tags=["Engagement"])
api_router.include_router(grc.router,        prefix="/grc",        tags=["GRC Integration"])
api_router.include_router(engine.router,     prefix="/engine",     tags=["Audit Engine"])
api_router.include_router(health.router,     prefix="",            tags=["Health"])
