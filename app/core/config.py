"""Application configuration settings."""

import os
from pathlib import Path


class Settings:
    """Application settings with environment-based configuration."""

    # Environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = ENVIRONMENT == "development"

    # Application
    APP_NAME: str = "Transcription Tool"
    APP_VERSION: str = "0.1.0"

    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    # Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    APP_DIR: Path = BASE_DIR / "app"
    TEMPLATES_DIR: Path = APP_DIR / "templates"
    STATIC_DIR: Path = APP_DIR / "static"
    UPLOADS_DIR: Path = BASE_DIR / "uploads"

    # Upload settings
    MAX_UPLOAD_SIZE: int = 500 * 1024 * 1024  # 500MB
    ALLOWED_VIDEO_EXTENSIONS: set[str] = {
        ".mp4",
        ".avi",
        ".mov",
        ".mkv",
        ".webm",
        ".m4v",
    }

    def __init__(self) -> None:
        """Ensure required directories exist."""
        self.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


settings = Settings()
