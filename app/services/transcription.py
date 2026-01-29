"""Mock transcription service with placeholder business logic.

This module contains mock implementations for:
- Video transcription
- Text summarization
- Meeting minutes extraction

In production, these functions would be replaced with actual AI/ML implementations.
"""

from app.models.schemas import (
    TranscriptionResponse,
    TimestampEntry,
    SummaryResponse,
    MeetingMinutesResponse,
    ActionItem,
)
from app.core.logging import get_logger

logger = get_logger("services.transcription")


def transcribe_video(
    file_path: str, include_timestamps: bool = True
) -> TranscriptionResponse:
    """Transcribe a video file to text.

    Args:
        file_path: Path to the video file.
        include_timestamps: Whether to include timestamps in the output.

    Returns:
        TranscriptionResponse with transcription text and optional timestamps.
    """
    logger.info(f"Transcribing video: {file_path}, timestamps: {include_timestamps}")

    # Mock transcription text
    full_text = """Welcome everyone to today's quarterly planning meeting. 
I'm Sarah, and I'll be leading today's discussion.

First, let's review our Q3 results. We exceeded our revenue targets by 15%, 
which is a great achievement for the team. John, would you like to share 
the breakdown?

Thanks Sarah. So looking at the numbers, our enterprise segment grew by 22%, 
while the SMB segment showed steady 8% growth. The new product line we 
launched in August has been particularly successful.

That's excellent news. Now let's discuss our Q4 priorities. 
We need to focus on three main areas: customer retention, 
product improvements, and expanding into new markets.

I'd like to propose that we allocate additional resources to the 
customer success team. Based on our data, improving retention by 
just 5% would have a significant impact on our bottom line.

Great point, Maria. Let's make that a priority. John, can you 
prepare a detailed proposal by next Friday?

Absolutely, I'll have that ready.

Perfect. Let's also discuss the timeline for the new feature release. 
The engineering team estimates we can have the beta ready by mid-November.

That works for our marketing timeline. We can coordinate the 
launch campaign accordingly.

Excellent. To summarize, our action items are: John will prepare 
the retention proposal, marketing will draft the launch plan, 
and we'll reconvene next week to review progress. 

Thanks everyone for your time today. Meeting adjourned."""

    # Extract filename from path
    video_filename = file_path.split("/")[-1] if "/" in file_path else file_path

    if include_timestamps:
        timestamps = [
            TimestampEntry(
                start_time=0.0,
                end_time=8.5,
                text="Welcome everyone to today's quarterly planning meeting. I'm Sarah, and I'll be leading today's discussion.",
            ),
            TimestampEntry(
                start_time=8.5,
                end_time=22.0,
                text="First, let's review our Q3 results. We exceeded our revenue targets by 15%, which is a great achievement for the team. John, would you like to share the breakdown?",
            ),
            TimestampEntry(
                start_time=22.0,
                end_time=38.0,
                text="Thanks Sarah. So looking at the numbers, our enterprise segment grew by 22%, while the SMB segment showed steady 8% growth. The new product line we launched in August has been particularly successful.",
            ),
            TimestampEntry(
                start_time=38.0,
                end_time=52.0,
                text="That's excellent news. Now let's discuss our Q4 priorities. We need to focus on three main areas: customer retention, product improvements, and expanding into new markets.",
            ),
            TimestampEntry(
                start_time=52.0,
                end_time=68.0,
                text="I'd like to propose that we allocate additional resources to the customer success team. Based on our data, improving retention by just 5% would have a significant impact on our bottom line.",
            ),
            TimestampEntry(
                start_time=68.0,
                end_time=82.0,
                text="Great point, Maria. Let's make that a priority. John, can you prepare a detailed proposal by next Friday?",
            ),
            TimestampEntry(
                start_time=82.0, end_time=86.0, text="Absolutely, I'll have that ready."
            ),
            TimestampEntry(
                start_time=86.0,
                end_time=98.0,
                text="Perfect. Let's also discuss the timeline for the new feature release. The engineering team estimates we can have the beta ready by mid-November.",
            ),
            TimestampEntry(
                start_time=98.0,
                end_time=108.0,
                text="That works for our marketing timeline. We can coordinate the launch campaign accordingly.",
            ),
            TimestampEntry(
                start_time=108.0,
                end_time=128.0,
                text="Excellent. To summarize, our action items are: John will prepare the retention proposal, marketing will draft the launch plan, and we'll reconvene next week to review progress.",
            ),
            TimestampEntry(
                start_time=128.0,
                end_time=135.0,
                text="Thanks everyone for your time today. Meeting adjourned.",
            ),
        ]
        logger.debug(f"Generated {len(timestamps)} timestamp entries")
        return TranscriptionResponse(
            text=full_text, timestamps=timestamps, video_filename=video_filename
        )

    return TranscriptionResponse(
        text=full_text, timestamps=None, video_filename=video_filename
    )


def summarize_text(text: str) -> SummaryResponse:
    """Summarize the given text.

    Args:
        text: The text to summarize.

    Returns:
        SummaryResponse with the summarized text.
    """
    logger.info(f"Summarizing text of length: {len(text)} characters")

    # Mock summary
    summary = """**Meeting Summary**

This quarterly planning meeting reviewed Q3 results and set Q4 priorities.

**Key Highlights:**
- Q3 revenue exceeded targets by 15%
- Enterprise segment grew 22%, SMB segment grew 8%
- New product line launched in August performing well

**Q4 Focus Areas:**
1. Customer retention improvement
2. Product enhancements
3. New market expansion

**Key Decisions:**
- Allocate additional resources to customer success team
- Beta release targeted for mid-November
- Marketing campaign to be coordinated with product launch

**Next Steps:**
- Retention proposal due next Friday
- Follow-up meeting scheduled for next week"""

    return SummaryResponse(summary=summary)


def extract_meeting_minutes(text: str) -> MeetingMinutesResponse:
    """Extract structured meeting minutes from transcription text.

    Args:
        text: The transcription text to analyze.

    Returns:
        MeetingMinutesResponse with structured meeting information.
    """
    logger.info(
        f"Extracting meeting minutes from text of length: {len(text)} characters"
    )

    # Mock meeting minutes
    return MeetingMinutesResponse(
        attendees=["Sarah (Meeting Lead)", "John", "Maria"],
        agenda_items=[
            "Q3 Results Review",
            "Q4 Priority Planning",
            "Customer Retention Strategy",
            "New Feature Release Timeline",
            "Marketing Campaign Coordination",
        ],
        action_items=[
            ActionItem(
                task="Prepare detailed customer retention proposal",
                assignee="John",
                due_date="Next Friday",
            ),
            ActionItem(
                task="Draft product launch marketing plan",
                assignee="Marketing Team",
                due_date="Before November release",
            ),
            ActionItem(
                task="Prepare beta release for new features",
                assignee="Engineering Team",
                due_date="Mid-November",
            ),
            ActionItem(
                task="Schedule follow-up meeting",
                assignee="Sarah",
                due_date="Next week",
            ),
        ],
        decisions=[
            "Allocate additional resources to customer success team",
            "Target 5% improvement in customer retention",
            "Beta release scheduled for mid-November",
            "Marketing campaign to align with product launch timeline",
        ],
    )
