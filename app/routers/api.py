"""API endpoints for transcription operations."""

import asyncio

import aiofiles
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from sse_starlette.sse import EventSourceResponse

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
from app.models.schemas import JobStatus, TranscriptionResponse
from app.services.transcription import summarize_text, extract_meeting_minutes
from app.services import job_manager

logger = get_logger("routers.api")
router = APIRouter(prefix="/api", tags=["API"])


@router.post("/upload")
async def upload_video(
    request: Request,
    response: Response,
    file: UploadFile = File(...),
    language: str = Form(default=""),
) -> JSONResponse:
    """Upload a video file and submit a transcription job.

    Instead of blocking until transcription completes, this endpoint:
    1. Saves the file
    2. Creates a background transcription job
    3. Returns the job_id immediately

    The frontend then connects to the SSE endpoint to receive progress updates.
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
        add_session_file(session_id, file_path)
    except Exception as e:
        logger.error(f"Failed to save file: {e}")
        raise HTTPException(status_code=500, detail="Failed to save uploaded file")

    # Create and submit job
    lang = language.strip() or None
    job_id = job_manager.create_job(
        session_id=session_id,
        file_path=str(file_path),
        video_filename=original_name,
        language=lang,
    )
    job_manager.submit_job(job_id)

    # Store job_id in session for later use
    update_session_data(session_id, "current_job_id", job_id)

    json_response = JSONResponse({"job_id": job_id, "message": "Job submitted"})
    # Copy session cookie to json response
    for key, value in response.headers.items():
        if key.lower() == "set-cookie":
            json_response.headers.append(key, value)
    return json_response


@router.get("/jobs/{job_id}/stream")
async def job_stream(job_id: str, request: Request) -> EventSourceResponse:
    """SSE endpoint that streams transcription job progress.

    Uses polling with a version counter for thread-safe change detection.
    The worker thread updates the job dict and increments a version counter;
    this endpoint polls every 300ms and emits SSE events when changes are detected.
    """
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator():
        last_version = -1

        while True:
            if await request.is_disconnected():
                break

            current_version = job_manager.get_job_version(job_id)
            if current_version != last_version:
                last_version = current_version
                progress = job_manager.get_job_progress(job_id)
                if progress:
                    yield {
                        "event": "progress",
                        "data": progress.model_dump_json(),
                    }
                    if progress.status in (JobStatus.COMPLETED, JobStatus.FAILED):
                        break

            await asyncio.sleep(0.3)

    return EventSourceResponse(event_generator())


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str) -> JSONResponse:
    """Get the current status of a transcription job."""
    progress = job_manager.get_job_progress(job_id)
    if not progress:
        raise HTTPException(status_code=404, detail="Job not found")
    return JSONResponse(progress.model_dump(mode="json"))


@router.get("/jobs/{job_id}/result")
async def get_job_result(
    job_id: str,
    request: Request,
    response: Response,
    include_timestamps: bool = True,
) -> HTMLResponse:
    """Get the transcription result as an HTML partial once the job is done.

    Called by the frontend after the SSE stream signals completion.
    """
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] != JobStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Job not yet completed")

    transcription: TranscriptionResponse = job["result"]

    # Store in session for summarize/minutes/download
    session_id = get_or_create_session(request, response)
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

    templates = request.app.state.templates
    return templates.TemplateResponse(
        "partials/transcription.html",
        {
            "request": request,
            "transcription": transcription,
            "include_timestamps": include_timestamps,
        },
    )


@router.post("/transcribe")
async def retranscribe(
    request: Request,
    response: Response,
    include_timestamps: bool = Form(default=True),
) -> HTMLResponse:
    """Re-render transcription with updated timestamp setting."""
    logger.debug(f"Re-transcribing with timestamps: {include_timestamps}")

    session_id = get_or_create_session(request, response)
    session_data = get_session_data(session_id)
    transcription_data = session_data.get("transcription", {})

    if not transcription_data.get("text"):
        raise HTTPException(status_code=400, detail="No transcription available")

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
    """Summarize the current transcription."""
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
    """Extract meeting minutes from the current transcription."""
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
    """Download the current transcription as a text file."""
    logger.info("Download transcription requested")

    session_id = get_or_create_session(request, response)
    session_prefix = get_session_file_prefix(session_id)
    session_data = get_session_data(session_id)
    transcription_data = session_data.get("transcription", {})

    if not transcription_data.get("text"):
        raise HTTPException(status_code=400, detail="No transcription available")

    download_path = settings.UPLOADS_DIR / f"{session_prefix}_transcription.txt"

    content = transcription_data["text"]

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

    add_session_file(session_id, download_path)

    return FileResponse(
        path=download_path, filename="transcription.txt", media_type="text/plain"
    )


@router.post("/session/end")
async def end_session(request: Request, response: Response) -> JSONResponse:
    """End the current session and clean up all associated files."""
    logger.info("Session end requested")

    session_id = request.cookies.get(settings.SESSION_COOKIE_NAME)

    if not session_id:
        return JSONResponse(
            {"success": True, "message": "No active session", "files_deleted": 0}
        )

    result = cleanup_session(session_id)

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
    """Get the current size of the uploads folder."""
    total_size = 0
    try:
        if settings.UPLOADS_DIR.exists():
            for file in settings.UPLOADS_DIR.iterdir():
                if file.is_file():
                    total_size += file.stat().st_size
    except Exception as e:
        logger.error(f"Failed to calculate uploads size: {e}")

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
