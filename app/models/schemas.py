"""Pydantic data models for request/response validation."""

from pydantic import BaseModel, Field


class TimestampEntry(BaseModel):
    """A single timestamped text segment."""

    start_time: float = Field(..., description="Start time in seconds")
    end_time: float = Field(..., description="End time in seconds")
    text: str = Field(..., description="Transcribed text for this segment")


class TranscriptionRequest(BaseModel):
    """Request model for transcription settings."""

    include_timestamps: bool = Field(
        default=True, description="Whether to include timestamps in the transcription"
    )


class TranscriptionResponse(BaseModel):
    """Response model for transcription results."""

    text: str = Field(..., description="Full transcription text")
    timestamps: list[TimestampEntry] | None = Field(
        default=None,
        description="List of timestamped segments if timestamps are enabled",
    )
    video_filename: str = Field(..., description="Original video filename")


class SummaryRequest(BaseModel):
    """Request model for summarization."""

    text: str = Field(..., description="Text to summarize")


class SummaryResponse(BaseModel):
    """Response model for summarization results."""

    summary: str = Field(..., description="Summarized text")


class ActionItem(BaseModel):
    """A single action item from meeting minutes."""

    task: str = Field(..., description="Description of the task")
    assignee: str | None = Field(default=None, description="Person responsible")
    due_date: str | None = Field(default=None, description="Due date if specified")


class MeetingMinutesRequest(BaseModel):
    """Request model for meeting minutes extraction."""

    text: str = Field(..., description="Transcription text to extract minutes from")


class MeetingMinutesResponse(BaseModel):
    """Response model for meeting minutes."""

    attendees: list[str] = Field(
        default_factory=list, description="List of meeting attendees"
    )
    agenda_items: list[str] = Field(
        default_factory=list, description="List of agenda items discussed"
    )
    action_items: list[ActionItem] = Field(
        default_factory=list, description="List of action items"
    )
    decisions: list[str] = Field(default_factory=list, description="Key decisions made")


class UploadResponse(BaseModel):
    """Response model for file upload."""

    filename: str = Field(..., description="Saved filename")
    file_path: str = Field(..., description="Path to saved file")
    message: str = Field(..., description="Status message")


class ErrorResponse(BaseModel):
    """Response model for errors."""

    error: str = Field(..., description="Error message")
    detail: str | None = Field(default=None, description="Additional error details")
