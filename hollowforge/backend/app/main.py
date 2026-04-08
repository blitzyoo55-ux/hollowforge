"""HollowForge FastAPI application entry point."""

from __future__ import annotations

import logging
import pathlib
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.db import init_db
from app.services.comfyui_client import ComfyUIClient
from app.services.favorite_upscale_service import FavoriteUpscaleService
from app.services.generation_service import GenerationService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _iter_public_data_dirs() -> tuple[pathlib.Path, ...]:
    return (
        settings.IMAGES_DIR,
        settings.IMAGES_DIR / "upscaled",
        settings.IMAGES_DIR / "adetailed",
        settings.IMAGES_DIR / "dreamactor",
        settings.IMAGES_DIR / "hiresfix",
        settings.IMAGES_DIR / "seedance",
        settings.IMAGES_DIR / "watermarked",
        settings.THUMBS_DIR,
        settings.WORKFLOWS_DIR,
        settings.COMICS_DIR,
        settings.COMICS_PREVIEWS_DIR,
        settings.COMICS_EXPORTS_DIR,
        settings.COMICS_MANIFESTS_DIR,
    )


def _ensure_public_data_dirs() -> None:
    for directory in _iter_public_data_dirs():
        directory.mkdir(parents=True, exist_ok=True)


def _mount_static_dirs(app: FastAPI) -> None:
    _ensure_public_data_dirs()
    app.mount(
        "/data/images/watermarked",
        StaticFiles(directory=str(settings.IMAGES_DIR / "watermarked")),
        name="data-images-watermarked",
    )
    app.mount(
        "/data/images",
        StaticFiles(directory=str(settings.IMAGES_DIR)),
        name="data-images",
    )
    app.mount(
        "/data/thumbs",
        StaticFiles(directory=str(settings.THUMBS_DIR)),
        name="data-thumbs",
    )
    app.mount(
        "/data/workflows",
        StaticFiles(directory=str(settings.WORKFLOWS_DIR)),
        name="data-workflows",
    )
    app.mount(
        "/data/comics/previews",
        StaticFiles(directory=str(settings.COMICS_PREVIEWS_DIR)),
        name="data-comics-previews",
    )
    app.mount(
        "/data/comics/exports",
        StaticFiles(directory=str(settings.COMICS_EXPORTS_DIR)),
        name="data-comics-exports",
    )
    app.mount(
        "/data/comics/manifests",
        StaticFiles(directory=str(settings.COMICS_MANIFESTS_DIR)),
        name="data-comics-manifests",
    )


def _include_routers(app: FastAPI, *, lightweight: bool = False) -> None:
    if lightweight:
        from app.routes import comic, sequences

        app.include_router(comic.router)
        app.include_router(sequences.router)
        return

    from app.routes import (
        animation,
        comic,
        collections,
        dreamactor,
        favorites,
        gallery,
        generations,
        loras,
        presets,
        publishing,
        reproduce,
        sequences,
        seedance,
        system,
    )
    from app.routes.export import router as export_router
    from app.routes.marketing import router as marketing_router
    from app.routes.quality_ai import router as quality_ai_router

    app.include_router(system.router)
    app.include_router(generations.router)
    app.include_router(animation.router)
    app.include_router(dreamactor.router)
    app.include_router(favorites.router)
    app.include_router(gallery.router)
    app.include_router(collections.router)
    app.include_router(presets.router)
    app.include_router(loras.router)
    app.include_router(publishing.router)
    app.include_router(reproduce.router)
    app.include_router(sequences.router)
    app.include_router(comic.router)
    app.include_router(export_router)
    app.include_router(seedance.router)
    app.include_router(quality_ai_router)
    app.include_router(marketing_router)

    if settings.LEAN_MODE:
        logger.info(
            "Lean mode enabled: advanced routers are disabled except Seedance, Quality AI, and Marketing."
        )
        return

    from app.routes import benchmark, moods, scheduler
    from app.routes.curation import router as curation_router

    app.include_router(moods.router)
    app.include_router(benchmark.router)
    app.include_router(scheduler.router)
    app.include_router(curation_router)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application startup and shutdown lifecycle."""
    # --- Startup ---
    if not getattr(app.state, "routers_initialized", False):
        _include_routers(app)
        app.state.routers_initialized = True

    logger.info("Initializing database...")
    await init_db()
    _ensure_public_data_dirs()

    # ComfyUI client
    comfyui_client = ComfyUIClient()
    app.state.comfyui_client = comfyui_client

    # Generation service + background worker
    gen_service = GenerationService(comfyui_client)
    app.state.generation_service = gen_service
    stale_count = await gen_service.cleanup_stale()
    logger.info("Startup stale generation cleanup complete: %d record(s) marked failed.", stale_count)
    gen_service.start_worker()
    logger.info("Generation worker started.")

    favorite_upscale_service = FavoriteUpscaleService(gen_service)
    app.state.favorite_upscale_service = favorite_upscale_service
    favorite_upscale_service.start()
    logger.info("Favorite upscale service initialized.")

    scheduler_service = None
    if settings.LEAN_MODE:
        logger.info("Lean mode enabled: scheduler service startup skipped.")
    else:
        from app.services.scheduler_service import SchedulerService

        scheduler_service = SchedulerService(gen_service)
        app.state.scheduler_service = scheduler_service
        await scheduler_service.start()
        logger.info("Scheduler service initialized.")

    yield

    # --- Shutdown ---
    if scheduler_service is not None:
        logger.info("Stopping scheduler service...")
        await scheduler_service.stop()
    logger.info("Stopping favorite upscale service...")
    await favorite_upscale_service.stop()
    logger.info("Shutting down generation worker...")
    await gen_service.shutdown()
    await comfyui_client.close()
    logger.info("Shutdown complete.")


@asynccontextmanager
async def _lightweight_lifespan(app: FastAPI) -> AsyncIterator[None]:
    _ensure_public_data_dirs()
    yield


def create_app(*, lightweight: bool = False) -> FastAPI:
    app = FastAPI(
        title="HollowForge",
        version="1.0.0",
        description="AI image generation management backend powered by ComfyUI",
        lifespan=_lightweight_lifespan if lightweight else lifespan,
    )

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

    _mount_static_dirs(app)
    app.state.routers_initialized = False
    if lightweight:
        _include_routers(app, lightweight=True)
        app.state.routers_initialized = True
    return app


app = create_app()
