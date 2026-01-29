"""Page routes for HTML templates."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.core.logging import get_logger

logger = get_logger("routers.pages")
router = APIRouter(tags=["Pages"])


@router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    """Render the main upload page.

    Args:
        request: FastAPI request object.

    Returns:
        HTMLResponse with the index page.
    """
    logger.debug("Rendering index page")
    templates = request.app.state.templates
    return templates.TemplateResponse("index.html", {"request": request})
