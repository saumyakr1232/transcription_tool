"""API endpoints for transcription operations."""

import aiofiles
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from app.core.config import settings
from app.core.logging import get_logger
from app.core.session import (
    get_or_create_session,
    get_session_data,
    update_session_data,
    add_session_file,
    cleanup_session,
    get_session_file_prefix,
)
from app.models.schemas import TranscriptionResponse
from app.services.transcription import (
    transcribe_video,
    summarize_text,
    extract_meeting_minutes,
)

logger = get_logger("routers.api")
router = APIRouter(prefix="/api", tags=["API"])


@router.post("/upload")
async def upload_video(
    request: Request,
    response: Response,
    file: UploadFile = File(...),
    include_timestamps: bool = Form(default=True),
) -> HTMLResponse:
    """Upload a video file and return transcription HTML partial.

    Args:
        request: FastAPI request object.
        response: FastAPI response object (for setting session cookie).
        file: Uploaded video file.
        include_timestamps: Whether to include timestamps in transcription.

    Returns:
        HTMLResponse with transcription partial HTML.
    """
    logger.info(f"Received file upload: {file.filename}, size: {file.size}")

    # Get or create session
    session_id = get_or_create_session(request, response)
    session_prefix = get_session_file_prefix(session_id)

    # Validate file extension
    if file.filename:
        ext = Path(file.filename).suffix.lower()
        if ext not in settings.ALLOWED_VIDEO_EXTENSIONS:
            logger.warning(f"Invalid file extension: {ext}")
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Allowed: {', '.join(settings.ALLOWED_VIDEO_EXTENSIONS)}",
            )

    # Generate unique filename with session prefix
    original_name = file.filename or "video"
    safe_name = "".join(c for c in original_name if c.isalnum() or c in ".-_")
    saved_filename = f"{session_prefix}_{safe_name}"
    file_path = settings.UPLOADS_DIR / saved_filename

    # Save file
    try:
        async with aiofiles.open(file_path, "wb") as f:
            content = await file.read()
            await f.write(content)
        logger.info(f"File saved: {file_path}")
        # Track file for session cleanup
        add_session_file(session_id, file_path)
    except Exception as e:
        logger.error(f"Failed to save file: {e}")
        raise HTTPException(status_code=500, detail="Failed to save uploaded file")

    # Transcribe
    try:
        transcription = transcribe_video(str(file_path), include_timestamps)

        # Store in session
        update_session_data(
            session_id,
            "transcription",
            {
                "text": transcription.text,
                "timestamps": transcription.timestamps,
                "video_filename": transcription.video_filename,
                "include_timestamps": include_timestamps,
            },
        )

        logger.info(f"Transcription complete for: {file.filename}")

        # Render partial template
        templates = request.app.state.templates
        html_response = templates.TemplateResponse(
            "partials/transcription.html",
            {
                "request": request,
                "transcription": transcription,
                "include_timestamps": include_timestamps,
            },
        )
        # Copy session cookie to template response
        for key, value in response.headers.items():
            if key.lower() == "set-cookie":
                html_response.headers.append(key, value)
        return html_response
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        raise HTTPException(status_code=500, detail="Transcription failed")


@router.post("/transcribe")
async def retranscribe(
    request: Request,
    response: Response,
    include_timestamps: bool = Form(default=True),
) -> HTMLResponse:
    """Re-render transcription with updated timestamp setting.

    Args:
        request: FastAPI request object.
        response: FastAPI response object.
        include_timestamps: Whether to include timestamps.

    Returns:
        HTMLResponse with updated transcription partial.
    """
    logger.debug(f"Re-transcribing with timestamps: {include_timestamps}")

    session_id = get_or_create_session(request, response)
    session_data = get_session_data(session_id)
    transcription_data = session_data.get("transcription", {})

    if not transcription_data.get("text"):
        raise HTTPException(status_code=400, detail="No transcription available")

    # Update timestamp setting
    transcription_data["include_timestamps"] = include_timestamps
    update_session_data(session_id, "transcription", transcription_data)

    transcription = TranscriptionResponse(
        text=transcription_data["text"],
        timestamps=transcription_data["timestamps"] if include_timestamps else None,
        video_filename=transcription_data.get("video_filename", "video"),
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
async def summarize(request: Request, response: Response) -> HTMLResponse:
    """Summarize the current transcription.

    Args:
        request: FastAPI request object.
        response: FastAPI response object.

    Returns:
        HTMLResponse with summary partial.
    """
    logger.info("Summarization requested")

    session_id = get_or_create_session(request, response)
    session_data = get_session_data(session_id)
    transcription_data = session_data.get("transcription", {})

    if not transcription_data.get("text"):
        raise HTTPException(status_code=400, detail="No transcription available")

    summary = summarize_text(transcription_data["text"])

    templates = request.app.state.templates
    return templates.TemplateResponse(
        "partials/summary.html", {"request": request, "summary": summary}
    )


@router.post("/meeting-minutes")
async def meeting_minutes(request: Request, response: Response) -> HTMLResponse:
    """Extract meeting minutes from the current transcription.

    Args:
        request: FastAPI request object.
        response: FastAPI response object.

    Returns:
        HTMLResponse with meeting minutes partial.
    """
    logger.info("Meeting minutes extraction requested")

    session_id = get_or_create_session(request, response)
    session_data = get_session_data(session_id)
    transcription_data = session_data.get("transcription", {})

    if not transcription_data.get("text"):
        raise HTTPException(status_code=400, detail="No transcription available")

    minutes = extract_meeting_minutes(transcription_data["text"])

    templates = request.app.state.templates
    return templates.TemplateResponse(
        "partials/meeting_minutes.html", {"request": request, "minutes": minutes}
    )


@router.get("/download")
async def download_transcription(request: Request, response: Response) -> FileResponse:
    """Download the current transcription as a text file.

    Args:
        request: FastAPI request object.
        response: FastAPI response object.

    Returns:
        FileResponse with transcription.txt file.
    """
    logger.info("Download transcription requested")

    session_id = get_or_create_session(request, response)
    session_prefix = get_session_file_prefix(session_id)
    session_data = get_session_data(session_id)
    transcription_data = session_data.get("transcription", {})

    if not transcription_data.get("text"):
        raise HTTPException(status_code=400, detail="No transcription available")

    # Create session-specific download file
    download_path = settings.UPLOADS_DIR / f"{session_prefix}_transcription.txt"

    content = transcription_data["text"]

    # Add timestamps if available and enabled
    if transcription_data.get("include_timestamps") and transcription_data.get(
        "timestamps"
    ):
        content = "TRANSCRIPTION WITH TIMESTAMPS\n" + "=" * 40 + "\n\n"
        for entry in transcription_data["timestamps"]:
            start = (
                f"{int(entry.start_time // 60):02d}:{int(entry.start_time % 60):02d}"
            )
            end = f"{int(entry.end_time // 60):02d}:{int(entry.end_time % 60):02d}"
            content += f"[{start} - {end}]\n{entry.text}\n\n"

    async with aiofiles.open(download_path, "w") as f:
        await f.write(content)

    # Track for cleanup
    add_session_file(session_id, download_path)

    return FileResponse(
        path=download_path, filename="transcription.txt", media_type="text/plain"
    )


@router.post("/session/end")
async def end_session(request: Request, response: Response) -> JSONResponse:
    """End the current session and clean up all associated files.

    Args:
        request: FastAPI request object.
        response: FastAPI response object.

    Returns:
        JSONResponse with cleanup results.
    """
    logger.info("Session end requested")

    session_id = request.cookies.get(settings.SESSION_COOKIE_NAME)

    if not session_id:
        return JSONResponse(
            {"success": True, "message": "No active session", "files_deleted": 0}
        )

    result = cleanup_session(session_id)

    # Clear the session cookie
    response.delete_cookie(settings.SESSION_COOKIE_NAME)

    return JSONResponse(
        {
            "success": True,
            "message": "Session ended and files cleaned up",
            "files_deleted": result["files_deleted"],
            "errors": result["errors"],
        }
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
