"""Session management for anonymous user sessions.

This module provides session management functionality:
- UUID-based anonymous sessions stored in-memory
- Session data isolation for multi-user support
- Automatic file cleanup when sessions end
"""

import uuid
from pathlib import Path
from datetime import datetime
from typing import Any
from fastapi import Request, Response

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("core.session")

# In-memory session store: session_id -> session_data
_sessions: dict[str, dict[str, Any]] = {}


def get_or_create_session(request: Request, response: Response) -> str:
    """Get existing session ID from cookie or create a new one.

    Args:
        request: FastAPI request object.
        response: FastAPI response object (to set cookie).

    Returns:
        Session ID string.
    """
    session_id = request.cookies.get(settings.SESSION_COOKIE_NAME)

    if session_id and session_id in _sessions:
        logger.debug(f"Existing session found: {session_id[:8]}...")
        return session_id

    # Create new session
    session_id = uuid.uuid4().hex
    _sessions[session_id] = {
        "created_at": datetime.now(),
        "transcription": {},
        "files": [],  # List of file paths created by this session
    }

    # Set cookie
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=session_id,
        max_age=settings.SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
    )

    logger.info(f"Created new session: {session_id[:8]}...")
    return session_id


def get_session_data(session_id: str) -> dict[str, Any]:
    """Get session data for a session ID.

    Args:
        session_id: The session ID.

    Returns:
        Session data dict, or empty dict if session doesn't exist.
    """
    return _sessions.get(session_id, {})


def update_session_data(session_id: str, key: str, value: Any) -> None:
    """Update a specific key in session data.

    Args:
        session_id: The session ID.
        key: The key to update.
        value: The value to set.
    """
    if session_id in _sessions:
        _sessions[session_id][key] = value
        logger.debug(f"Updated session {session_id[:8]}... key: {key}")


def add_session_file(session_id: str, file_path: Path | str) -> None:
    """Track a file created by a session for later cleanup.

    Args:
        session_id: The session ID.
        file_path: Path to the file to track.
    """
    if session_id in _sessions:
        file_path = Path(file_path) if isinstance(file_path, str) else file_path
        _sessions[session_id]["files"].append(file_path)
        logger.debug(f"Tracked file for session {session_id[:8]}...: {file_path.name}")


def cleanup_session(session_id: str) -> dict[str, Any]:
    """Clean up a session and delete all associated files.

    Args:
        session_id: The session ID to clean up.

    Returns:
        Dict with cleanup results (files_deleted, errors).
    """
    result = {"files_deleted": 0, "errors": []}

    if session_id not in _sessions:
        logger.warning(f"Session not found for cleanup: {session_id[:8]}...")
        return result

    session_data = _sessions[session_id]
    files = session_data.get("files", [])

    # Delete all tracked files
    for file_path in files:
        try:
            if file_path.exists():
                file_path.unlink()
                result["files_deleted"] += 1
                logger.debug(f"Deleted file: {file_path.name}")
        except Exception as e:
            error_msg = f"Failed to delete {file_path}: {e}"
            result["errors"].append(error_msg)
            logger.error(error_msg)

    # Remove session from store
    del _sessions[session_id]
    logger.info(
        f"Session {session_id[:8]}... cleaned up. "
        f"Files deleted: {result['files_deleted']}"
    )

    return result


def get_session_file_prefix(session_id: str) -> str:
    """Get the file prefix for a session (used for unique filenames).

    Args:
        session_id: The session ID.

    Returns:
        Prefix string (first 8 chars of session ID).
    """
    return session_id[:8]


def cleanup_stale_sessions(max_age_seconds: int | None = None) -> int:
    """Clean up sessions older than max age.

    Args:
        max_age_seconds: Max age in seconds. Defaults to SESSION_MAX_AGE.

    Returns:
        Number of sessions cleaned up.
    """
    if max_age_seconds is None:
        max_age_seconds = settings.SESSION_MAX_AGE

    now = datetime.now()
    stale_sessions = []

    for session_id, data in _sessions.items():
        created_at = data.get("created_at")
        if created_at:
            age = (now - created_at).total_seconds()
            if age > max_age_seconds:
                stale_sessions.append(session_id)

    for session_id in stale_sessions:
        cleanup_session(session_id)

    if stale_sessions:
        logger.info(f"Cleaned up {len(stale_sessions)} stale sessions")

    return len(stale_sessions)
