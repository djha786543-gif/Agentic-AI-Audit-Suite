"""
api/v1/api_router.py  ← REPLACE your existing file with this
────────────────────
Adds the new /engine/* endpoints to the existing router.
"""
from fastapi import APIRouter
from api.v1.endpoints import audit, auth, evaluation, health
from api.v1.endpoints import engine   # ← NEW

api_router = APIRouter()

api_router.include_router(health.router,      prefix="/health",     tags=["Health"])
api_router.include_router(auth.router,        prefix="/auth",       tags=["Auth"])
api_router.include_router(audit.router,       prefix="/audit",      tags=["Audit Vault"])
api_router.include_router(evaluation.router,  prefix="/evaluation", tags=["Evaluations"])
api_router.include_router(engine.router,      prefix="/engine",     tags=["Audit Engine"])  # ← NEW
