"""Job manager for background transcription tasks.

Uses a ThreadPoolExecutor for I/O-bound work (file saving, ffmpeg conversion)
and delegates CPU/GPU-bound transcription to the WhisperTranscriber.
Jobs are tracked in-memory with polling-based progress updates for SSE.
"""

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any

from app.core.logging import get_logger
from app.models.schemas import (
    JobProgress,
    JobStatus,
    TranscriptionResponse,
)

logger = get_logger("services.job_manager")

# In-memory job store: job_id -> job data
_jobs: dict[str, dict[str, Any]] = {}

# Worker pool for running transcription in background threads
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="transcription-worker")


def create_job(
    session_id: str,
    file_path: str,
    video_filename: str,
    language: str | None = None,
) -> str:
    """Create a new transcription job.

    Args:
        session_id: The session that owns this job.
        file_path: Path to the uploaded video file.
        video_filename: Original filename for display.
        language: Optional language code for transcription.

    Returns:
        The new job ID.
    """
    job_id = uuid.uuid4().hex[:12]
    _jobs[job_id] = {
        "job_id": job_id,
        "session_id": session_id,
        "file_path": file_path,
        "video_filename": video_filename,
        "language": language,
        "status": JobStatus.QUEUED,
        "progress": 0,
        "message": "Job queued",
        "result": None,
        "error": None,
        "created_at": datetime.now(),
        "_version": 0,
    }
    logger.info(f"Created job {job_id} for session {session_id[:8]}...")
    return job_id


def get_job(job_id: str) -> dict[str, Any] | None:
    """Get job data by ID."""
    return _jobs.get(job_id)


def get_job_progress(job_id: str) -> JobProgress | None:
    """Get current job progress as a Pydantic model."""
    job = _jobs.get(job_id)
    if not job:
        return None
    return JobProgress(
        job_id=job["job_id"],
        status=job["status"],
        progress=job["progress"],
        message=job["message"],
        result=job["result"],
        error=job["error"],
    )


def get_job_version(job_id: str) -> int:
    """Get the current version counter for change detection."""
    job = _jobs.get(job_id)
    return job["_version"] if job else -1


def _update_job(
    job_id: str,
    status: JobStatus,
    progress: int,
    message: str,
    result: TranscriptionResponse | None = None,
    error: str | None = None,
) -> None:
    """Update job state from the worker thread.

    The SSE endpoint polls for changes using the _version counter,
    so no async queue synchronization is needed.
    """
    job = _jobs.get(job_id)
    if not job:
        return

    job["status"] = status
    job["progress"] = progress
    job["message"] = message
    job["result"] = result
    job["error"] = error
    job["_version"] += 1

    logger.debug(f"Job {job_id}: {status.value} ({progress}%) - {message}")


def run_transcription_job(job_id: str) -> None:
    """Execute transcription in a worker thread.

    This function is submitted to the ThreadPoolExecutor and calls
    the WhisperTranscriber synchronously. Progress updates are pushed
    via _update_job which increments the version counter for SSE polling.
    """
    job = _jobs.get(job_id)
    if not job:
        logger.error(f"Job {job_id} not found when starting worker")
        return

    file_path = job["file_path"]
    video_filename = job["video_filename"]
    language = job["language"]

    try:
        # Step 1: Loading model
        _update_job(job_id, JobStatus.LOADING_MODEL, 10, "Loading Whisper model...")

        from app.services.transcriber import WhisperTranscriber

        transcriber = WhisperTranscriber()
        transcriber.load_model()

        # Step 2: Converting audio with ffmpeg
        _update_job(job_id, JobStatus.CONVERTING, 30, "Converting audio with ffmpeg...")

        # Step 3: Transcribing
        _update_job(job_id, JobStatus.TRANSCRIBING, 50, "Transcribing audio...")

        result = transcriber.transcribe_file(file_path, language=language)

        # Build response
        transcription = TranscriptionResponse(
            text=result["text"],
            timestamps=result.get("timestamps"),
            video_filename=video_filename,
        )

        # Step 4: Done
        _update_job(
            job_id,
            JobStatus.COMPLETED,
            100,
            "Transcription complete!",
            result=transcription,
        )

        # Cleanup transcriber resources
        transcriber.cleanup()

    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}", exc_info=True)
        _update_job(
            job_id, JobStatus.FAILED, 0, f"Transcription failed: {e}", error=str(e)
        )


def submit_job(job_id: str) -> None:
    """Submit a job to the worker pool for background execution."""
    _executor.submit(run_transcription_job, job_id)
    logger.info(f"Job {job_id} submitted to worker pool")


def cleanup_job(job_id: str) -> None:
    """Remove a job from the store."""
    _jobs.pop(job_id, None)


def shutdown_executor() -> None:
    """Shutdown the thread pool (call on app shutdown)."""
    _executor.shutdown(wait=False)
    logger.info("Worker pool shut down")
