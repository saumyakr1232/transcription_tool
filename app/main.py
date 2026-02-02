"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging import logger, get_logger
from app.core.session import cleanup_stale_sessions
from app.services.job_manager import shutdown_executor
from app.routers import api, pages

app_logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Debug mode: {settings.DEBUG}")
    yield
    # Shutdown worker pool
    logger.info("Shutting down worker pool...")
    shutdown_executor()
    # Cleanup all sessions on shutdown
    logger.info("Cleaning up sessions...")
    cleanup_stale_sessions(max_age_seconds=0)  # Clean all sessions
    logger.info("Shutting down application")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
    lifespan=lifespan,
)

# Mount static files
app.mount("/static", StaticFiles(directory=settings.STATIC_DIR), name="static")

# Setup templates
templates = Jinja2Templates(directory=settings.TEMPLATES_DIR)
app.state.templates = templates

# Include routers
app.include_router(pages.router)
app.include_router(api.router)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests."""
    app_logger.info(f"{request.method} {request.url.path}")
    response = await call_next(request)
    app_logger.debug(f"Response status: {response.status_code}")
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle uncaught exceptions."""
    app_logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if settings.DEBUG else None,
        },
    )
