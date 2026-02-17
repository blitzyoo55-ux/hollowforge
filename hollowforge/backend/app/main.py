"""HollowForge FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.db import init_db
from app.routes import gallery, generations, loras, presets, reproduce, system
from app.services.comfyui_client import ComfyUIClient
from app.services.generation_service import GenerationService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application startup and shutdown lifecycle."""
    # --- Startup ---
    logger.info("Initializing database...")
    await init_db()

    # Ensure data directories exist
    for d in (settings.IMAGES_DIR, settings.THUMBS_DIR, settings.WORKFLOWS_DIR):
        d.mkdir(parents=True, exist_ok=True)

    # ComfyUI client
    comfyui_client = ComfyUIClient()
    app.state.comfyui_client = comfyui_client

    # Generation service + background worker
    gen_service = GenerationService()
    app.state.generation_service = gen_service
    gen_service.start_worker()
    logger.info("Generation worker started.")

    yield

    # --- Shutdown ---
    logger.info("Shutting down generation worker...")
    await gen_service.shutdown()
    await comfyui_client.close()
    logger.info("Shutdown complete.")


app = FastAPI(
    title="HollowForge",
    version="1.0.0",
    description="AI image generation management backend powered by ComfyUI",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files for generated images, thumbnails, workflows
app.mount("/data", StaticFiles(directory=str(settings.DATA_DIR)), name="data")

# Routers
app.include_router(system.router)
app.include_router(generations.router)
app.include_router(gallery.router)
app.include_router(presets.router)
app.include_router(loras.router)
app.include_router(reproduce.router)
