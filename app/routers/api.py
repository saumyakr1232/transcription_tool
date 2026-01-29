"""API endpoints for transcription operations."""

import uuid
import aiofiles
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse

from app.core.config import settings
from app.core.logging import get_logger
from app.models.schemas import ErrorResponse
from app.services.transcription import (
    transcribe_video,
    summarize_text,
    extract_meeting_minutes,
)

logger = get_logger("routers.api")
router = APIRouter(prefix="/api", tags=["API"])

# In-memory storage for current session (simplified - no auth/sessions)
_current_transcription: dict = {}


@router.post("/upload")
async def upload_video(
    request: Request,
    file: UploadFile = File(...),
    include_timestamps: bool = Form(default=True),
) -> HTMLResponse:
    """Upload a video file and return transcription HTML partial.

    Args:
        request: FastAPI request object.
        file: Uploaded video file.
        include_timestamps: Whether to include timestamps in transcription.

    Returns:
        HTMLResponse with transcription partial HTML.
    """
    logger.info(f"Received file upload: {file.filename}, size: {file.size}")

    # Validate file extension
    if file.filename:
        ext = Path(file.filename).suffix.lower()
        if ext not in settings.ALLOWED_VIDEO_EXTENSIONS:
            logger.warning(f"Invalid file extension: {ext}")
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Allowed: {', '.join(settings.ALLOWED_VIDEO_EXTENSIONS)}",
            )

    # Generate unique filename
    unique_id = uuid.uuid4().hex[:8]
    original_name = file.filename or "video"
    safe_name = "".join(c for c in original_name if c.isalnum() or c in ".-_")
    saved_filename = f"{unique_id}_{safe_name}"
    file_path = settings.UPLOADS_DIR / saved_filename

    # Save file
    try:
        async with aiofiles.open(file_path, "wb") as f:
            content = await file.read()
            await f.write(content)
        logger.info(f"File saved: {file_path}")
    except Exception as e:
        logger.error(f"Failed to save file: {e}")
        raise HTTPException(status_code=500, detail="Failed to save uploaded file")

    # Transcribe
    try:
        transcription = transcribe_video(str(file_path), include_timestamps)

        # Store for later use
        _current_transcription["text"] = transcription.text
        _current_transcription["timestamps"] = transcription.timestamps
        _current_transcription["video_filename"] = transcription.video_filename
        _current_transcription["include_timestamps"] = include_timestamps

        logger.info(f"Transcription complete for: {file.filename}")

        # Render partial template
        templates = request.app.state.templates
        return templates.TemplateResponse(
            "partials/transcription.html",
            {
                "request": request,
                "transcription": transcription,
                "include_timestamps": include_timestamps,
            },
        )
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        raise HTTPException(status_code=500, detail="Transcription failed")


@router.post("/transcribe")
async def retranscribe(
    request: Request,
    include_timestamps: bool = Form(default=True),
) -> HTMLResponse:
    """Re-render transcription with updated timestamp setting.

    Args:
        request: FastAPI request object.
        include_timestamps: Whether to include timestamps.

    Returns:
        HTMLResponse with updated transcription partial.
    """
    logger.debug(f"Re-transcribing with timestamps: {include_timestamps}")

    if not _current_transcription.get("text"):
        raise HTTPException(status_code=400, detail="No transcription available")

    # Update timestamp setting and re-fetch timestamps if needed
    _current_transcription["include_timestamps"] = include_timestamps

    from app.models.schemas import TranscriptionResponse

    transcription = TranscriptionResponse(
        text=_current_transcription["text"],
        timestamps=_current_transcription["timestamps"] if include_timestamps else None,
        video_filename=_current_transcription.get("video_filename", "video"),
    )

    templates = request.app.state.templates
    return templates.TemplateResponse(
        "partials/transcription.html",
        {
            "request": request,
            "transcription": transcription,
            "include_timestamps": include_timestamps,
        },
    )


@router.post("/summarize")
async def summarize(request: Request) -> HTMLResponse:
    """Summarize the current transcription.

    Args:
        request: FastAPI request object.

    Returns:
        HTMLResponse with summary partial.
    """
    logger.info("Summarization requested")

    if not _current_transcription.get("text"):
        raise HTTPException(status_code=400, detail="No transcription available")

    summary = summarize_text(_current_transcription["text"])

    templates = request.app.state.templates
    return templates.TemplateResponse(
        "partials/summary.html", {"request": request, "summary": summary}
    )


@router.post("/meeting-minutes")
async def meeting_minutes(request: Request) -> HTMLResponse:
    """Extract meeting minutes from the current transcription.

    Args:
        request: FastAPI request object.

    Returns:
        HTMLResponse with meeting minutes partial.
    """
    logger.info("Meeting minutes extraction requested")

    if not _current_transcription.get("text"):
        raise HTTPException(status_code=400, detail="No transcription available")

    minutes = extract_meeting_minutes(_current_transcription["text"])

    templates = request.app.state.templates
    return templates.TemplateResponse(
        "partials/meeting_minutes.html", {"request": request, "minutes": minutes}
    )


@router.get("/download")
async def download_transcription() -> FileResponse:
    """Download the current transcription as a text file.

    Returns:
        FileResponse with transcription.txt file.
    """
    logger.info("Download transcription requested")

    if not _current_transcription.get("text"):
        raise HTTPException(status_code=400, detail="No transcription available")

    # Create temporary file
    download_path = settings.UPLOADS_DIR / "transcription.txt"

    content = _current_transcription["text"]

    # Add timestamps if available and enabled
    if _current_transcription.get("include_timestamps") and _current_transcription.get(
        "timestamps"
    ):
        content = "TRANSCRIPTION WITH TIMESTAMPS\n" + "=" * 40 + "\n\n"
        for entry in _current_transcription["timestamps"]:
            start = (
                f"{int(entry.start_time // 60):02d}:{int(entry.start_time % 60):02d}"
            )
            end = f"{int(entry.end_time // 60):02d}:{int(entry.end_time % 60):02d}"
            content += f"[{start} - {end}]\n{entry.text}\n\n"

    async with aiofiles.open(download_path, "w") as f:
        await f.write(content)

    return FileResponse(
        path=download_path, filename="transcription.txt", media_type="text/plain"
    )


@router.get("/uploads-size")
async def get_uploads_size() -> HTMLResponse:
    """Get the current size of the uploads folder.

    Returns:
        HTMLResponse with formatted size.
    """
    total_size = 0
    try:
        if settings.UPLOADS_DIR.exists():
            for file in settings.UPLOADS_DIR.iterdir():
                if file.is_file():
                    total_size += file.stat().st_size
    except Exception as e:
        logger.error(f"Failed to calculate uploads size: {e}")

    # Format size
    if total_size == 0:
        formatted = "0 B"
    elif total_size < 1024:
        formatted = f"{total_size} B"
    elif total_size < 1024 * 1024:
        formatted = f"{total_size / 1024:.1f} KB"
    elif total_size < 1024 * 1024 * 1024:
        formatted = f"{total_size / (1024 * 1024):.1f} MB"
    else:
        formatted = f"{total_size / (1024 * 1024 * 1024):.2f} GB"

    return HTMLResponse(f"Uploads: {formatted}")
