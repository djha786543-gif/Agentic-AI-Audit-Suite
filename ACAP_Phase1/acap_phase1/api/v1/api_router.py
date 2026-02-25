from fastapi import APIRouter
from api.v1.endpoints import audit, auth, intelligence

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["Security"])
api_router.include_router(audit.router, prefix="/audit", tags=["Audit Vault"])
api_router.include_router(intelligence.router, prefix="/intelligence", tags=["Intelligence"])
