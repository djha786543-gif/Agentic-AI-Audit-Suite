"""api/v1/api_router.py — all routers registered"""
from fastapi import APIRouter
from api.v1.endpoints import audit, auth, health, engagement, grc, engine, connectors
from api.v1.endpoints import evaluation
from api.v1.endpoints import governance, alerts, reports
from api.v1.endpoints import uat

api_router = APIRouter()
api_router.include_router(auth.router,        prefix="/auth",        tags=["Auth"])
api_router.include_router(audit.router,       prefix="/audit",       tags=["Evidence Vault"])
api_router.include_router(engagement.router,  prefix="/engagement",  tags=["Engagement"])
api_router.include_router(grc.router,         prefix="/grc",         tags=["GRC Integration"])
api_router.include_router(engine.router,      prefix="/engine",      tags=["Audit Engine"])
api_router.include_router(evaluation.router,  prefix="/evaluation",  tags=["Evaluation"])
api_router.include_router(connectors.router,  prefix="/connectors",  tags=["Connectors"])
# Phase 5 — Continuous Assurance & Governance
api_router.include_router(governance.router,  prefix="/governance",  tags=["Governance"])
api_router.include_router(alerts.router,      prefix="/alerts",      tags=["Compliance Alerts"])
# Phase 6 — Enterprise Reporting
api_router.include_router(reports.router,     prefix="/reports",     tags=["Enterprise Reports"])
api_router.include_router(uat.router,         prefix="/uat",         tags=["UAT Reports"])
api_router.include_router(health.router,      prefix="",             tags=["Health"])

