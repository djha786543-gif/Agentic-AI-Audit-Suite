"""
main.py — ACAP FastAPI application
Serves the API + your custom index.html dashboard on /
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import os
import logging

from api.v1.api_router import api_router
from core.config import settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("ACAP starting — env=%s", settings.ENVIRONMENT)
    from init_db import init_db
    init_db()
    logger.info("DB tables ready with RLS")
    yield
    logger.info("ACAP shutdown")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.1.0",
    docs_url="/docs",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)


from fastapi.staticfiles import StaticFiles
frontend_path = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
else:
    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def dashboard():
        return HTMLResponse(content="<h1>ACAP API running — <a href='/docs'>Open Docs</a></h1>")
