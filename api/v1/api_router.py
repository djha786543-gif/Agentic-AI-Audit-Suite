"""api/v1/api_router.py — all routers registered"""
from fastapi import APIRouter
from api.v1.endpoints import audit, auth, health, evaluation

api_router = APIRouter()
api_router.include_router(auth.router,   prefix="/auth",   tags=["Auth"])
api_router.include_router(audit.router,  prefix="/audit",  tags=["Evidence Vault"])
api_router.include_router(evaluation.router, prefix="/evaluation", tags=["Evaluations"])
api_router.include_router(health.router, prefix="",        tags=["Health"])
