"""Job manager for background transcription tasks.

Uses multiprocessing.Process for heavy transcription jobs to support
cancellation (termination) and isolation.
Updates are sent back to the main process via a multiprocessing.Queue.
"""

import multiprocessing
import threading
import uuid
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

# Map job_id -> Process object
_processes: dict[str, multiprocessing.Process] = {}

# Queue for receiving updates from worker processes
# Message format: (job_id, status, progress, message, result, error)
_status_queue: multiprocessing.Queue = multiprocessing.Queue()

# Listener thread for the queue
_listener_thread: threading.Thread | None = None
_stop_listener = threading.Event()


def _worker_process(
    job_id: str,
    file_path: str,
    video_filename: str,
    language: str | None,
    queue: multiprocessing.Queue,
) -> None:
    """Worker function acting as the transcription process."""
    try:
        # Helper to send updates
        def send_update(
            s: JobStatus,
            p: int,
            m: str,
            r: TranscriptionResponse | None = None,
            e: str | None = None,
        ):
            queue.put((job_id, s, p, m, r, e))

        # --- TQDM Hook ---
        # We need a way to capture tqdm output from Whisper (or any other lib).
        # We'll create a custom class and monkeypatch tqdm.tqdm.
        import tqdm

        class TqdmToQueue(tqdm.tqdm):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                # Ensure we don't spam updates; simple throttle could be added here

            def update(self, n=1):
                super().update(n)
                # Calculate percentage
                if self.total:
                    pct = int((self.n / self.total) * 100)
                    # We map TQDM progress (0-100) to Job Progress.
                    # Let's say Transcribing is 50% -> 90% of total job.
                    # So mapped_pct = 50 + (pct * 0.4)
                    mapped_pct = 50 + int(pct * 0.4)

                    # Only send update if significant change or sufficient time passed
                    # For simplicity, sending every update here (Queue is fast enough over IPC for reasonable chunks)
                    send_update(
                        JobStatus.TRANSCRIBING, mapped_pct, f"Transcribing: {pct}%"
                    )

            def close(self):
                super().close()

        # Apply the patch
        # Save original just in case (though process is ephemeral)
        _original_tqdm = tqdm.tqdm
        tqdm.tqdm = TqdmToQueue
        # ----------------

        # Check for cancellation is implicit: if we are terminated, we stop.

        # Step 1: Loading model
        send_update(JobStatus.LOADING_MODEL, 10, "Loading Whisper model...")

        from app.services.transcriber import WhisperTranscriber

        transcriber = WhisperTranscriber()
        transcriber.load_model()

        # Step 2: Converting audio with ffmpeg
        send_update(JobStatus.CONVERTING, 30, "Converting audio with ffmpeg...")

        # Step 3: Transcribing
        send_update(JobStatus.TRANSCRIBING, 50, "Transcribing audio...")

        result = transcriber.transcribe_file(file_path, language=language)

        # Build response
        transcription = TranscriptionResponse(
            text=result["text"],
            timestamps=result.get("timestamps"),
            video_filename=video_filename,
        )

        # Step 4: Done
        send_update(
            JobStatus.COMPLETED,
            100,
            "Transcription complete!",
            result=transcription,
        )

        transcriber.cleanup()

    except Exception as e:
        queue.put(
            (job_id, JobStatus.FAILED, 0, f"Transcription failed: {e}", None, str(e))
        )


def _start_listener_if_needed():
    """Start the background thread that consumes the status queue."""
    global _listener_thread
    if _listener_thread is None or not _listener_thread.is_alive():
        _stop_listener.clear()
        _listener_thread = threading.Thread(
            target=_status_queue_listener, daemon=True, name="job-manager-listener"
        )
        _listener_thread.start()
        logger.info("Started job manager status listener")


def _status_queue_listener():
    """Runs in a thread in the main process, updating the global _jobs dict."""
    while not _stop_listener.is_set():
        try:
            # Blocking get with timeout to allow checking stop_event
            msg = _status_queue.get(timeout=1.0)
            job_id, status, progress, message, result, error = msg

            _update_job_state(job_id, status, progress, message, result, error)

            # If job is done/failed, remove from process map if present
            if status in (JobStatus.COMPLETED, JobStatus.FAILED):
                if job_id in _processes:
                    # process join() is usually good practice, but we do it lazily or explicitly
                    _processes.pop(job_id, None)

        except multiprocessing.queues.Empty:
            continue
        except Exception as e:
            logger.error(f"Error in status listener: {e}")


def _update_job_state(
    job_id: str,
    status: JobStatus,
    progress: int,
    message: str,
    result: TranscriptionResponse | None = None,
    error: str | None = None,
) -> None:
    """Internal helper to update the in-memory job store."""
    job = _jobs.get(job_id)
    if not job:
        return

    # If explicitly cancelled by user, we might ignore delayed updates
    if job["status"] == JobStatus.CANCELLED:
        return

    job["status"] = status
    job["progress"] = progress
    job["message"] = message
    if result:
        job["result"] = result
    if error:
        job["error"] = error
    job["_version"] += 1
    logger.debug(f"Job {job_id}: {status.value} ({progress}%) - {message}")


def create_job(
    session_id: str,
    file_path: str,
    video_filename: str,
    language: str | None = None,
) -> str:
    """Create a new transcription job."""
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


def submit_job(job_id: str) -> None:
    """Submit a job to a background process."""
    job = _jobs.get(job_id)
    if not job:
        logger.error(f"Job {job_id} not found")
        return

    _start_listener_if_needed()

    p = multiprocessing.Process(
        target=_worker_process,
        args=(
            job_id,
            job["file_path"],
            job["video_filename"],
            job["language"],
            _status_queue,
        ),
        daemon=True,
    )
    p.start()
    _processes[job_id] = p
    logger.info(f"Started worker process for job {job_id} (PID: {p.pid})")


def stop_job(job_id: str) -> bool:
    """Stop a running job by terminating its process."""
    job = _jobs.get(job_id)
    if not job:
        return False

    if job["status"] in (
        JobStatus.COMPLETED,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
    ):
        return False

    # Mark as cancelled in state
    job["status"] = JobStatus.CANCELLED
    job["message"] = "Job stopped by user"
    job["_version"] += 1

    # Terminate process if it exists
    p = _processes.get(job_id)
    if p and p.is_alive():
        logger.warning(f"Terminating process {p.pid} for job {job_id}")
        p.terminate()
        p.join(timeout=1)
        if p.is_alive():
            p.kill()  # Force kill if terminate fails
        _processes.pop(job_id, None)

    logger.info(f"Job {job_id} stopped by user")
    return True


def get_job(job_id: str) -> dict[str, Any] | None:
    return _jobs.get(job_id)


def get_job_progress(job_id: str) -> JobProgress | None:
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
    job = _jobs.get(job_id)
    return job["_version"] if job else -1


def cleanup_job(job_id: str) -> None:
    stop_job(job_id)  # Ensure stopped before cleanup
    _jobs.pop(job_id, None)


def shutdown_executor() -> None:
    """Cleanup processes and listener thread."""
    logger.info("Shutting down job manager...")
    _stop_listener.set()

    # Terminate all running processes
    for job_id, p in list(_processes.items()):
        if p.is_alive():
            p.terminate()
            p.join(timeout=1)

    if _listener_thread and _listener_thread.is_alive():
        _listener_thread.join(timeout=2)

    logger.info("Job manager shutdown complete")
