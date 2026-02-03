"""WhisperTranscriber - Handles model loading, audio conversion, and transcription.

This module wraps the Whisper model for transcription. It:
1. Loads the Whisper model (CPU or GPU)
2. Uses ffmpeg to convert input video/audio to WAV format
3. Runs Whisper transcription on the WAV file
4. Cleans up temporary files (WAV, intermediate ffmpeg outputs)

Currently uses a mock implementation. Replace the body of each method
with real Whisper + ffmpeg calls for production use.
"""

import time
from pathlib import Path

from app.core.logging import get_logger

logger = get_logger("services.transcriber")


class WhisperTranscriber:
    """Transcription engine using OpenAI Whisper.

    Usage:
        transcriber = WhisperTranscriber()
        transcriber.load_model()
        result = transcriber.transcribe_file("/path/to/video.mp4", language="en")
        transcriber.cleanup()
    """

    def __init__(self, model_size: str = "base") -> None:
        self.model_size = model_size
        self.model = None
        self._temp_files: list[Path] = []

    def load_model(self) -> None:
        """Load the Whisper model into memory.

        In production, this would call:
            import whisper
            self.model = whisper.load_model(self.model_size)
        """
        logger.info(f"Loading Whisper model: {self.model_size}")
        # Simulate model loading time
        time.sleep(1.5)
        self.model = "mock_model"
        logger.info("Whisper model loaded")

    def transcribe_file(self, file_path: str, language: str | None = None) -> dict:
        """Convert video to WAV via ffmpeg, then transcribe with Whisper.

        Args:
            file_path: Path to the input video/audio file.
            language: Optional language code (e.g., "en", "es").

        Returns:
            Dict with keys:
                - text: Full transcription text
                - timestamps: List of TimestampEntry-compatible dicts
        """
        input_path = Path(file_path)
        wav_path = input_path.with_suffix(".wav")
        self._temp_files.append(wav_path)

        # Step 1: Convert to WAV with ffmpeg
        logger.info(f"Converting {input_path.name} to WAV with ffmpeg...")
        # In production:
        #   subprocess.run([
        #       "ffmpeg", "-i", str(input_path),
        #       "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
        #       str(wav_path), "-y"
        #   ], check=True, capture_output=True)
        time.sleep(2.0)  # Simulate ffmpeg conversion
        logger.info("Audio conversion complete")

        # Step 2: Transcribe with Whisper
        logger.info("Running Whisper transcription...")

        # In production:
        #   result = self.model.transcribe(
        #       str(wav_path), language=language, verbose=False
        #   )

        # Simulate transcription with progress bars to test the TqdmToQueue hook
        from tqdm import tqdm

        for _ in tqdm(range(100), desc="Transcribing"):
            time.sleep(0.03)  # 3 seconds total

        # time.sleep(3.0)  # Old simulation

        # Mock result
        full_text = (
            "Welcome everyone to today's quarterly planning meeting. "
            "I'm Sarah, and I'll be leading today's discussion.\n\n"
            "First, let's review our Q3 results. We exceeded our revenue targets by 15%, "
            "which is a great achievement for the team. John, would you like to share "
            "the breakdown?\n\n"
            "Thanks Sarah. So looking at the numbers, our enterprise segment grew by 22%, "
            "while the SMB segment showed steady 8% growth. The new product line we "
            "launched in August has been particularly successful.\n\n"
            "That's excellent news. Now let's discuss our Q4 priorities. "
            "We need to focus on three main areas: customer retention, "
            "product improvements, and expanding into new markets.\n\n"
            "I'd like to propose that we allocate additional resources to the "
            "customer success team. Based on our data, improving retention by "
            "just 5% would have a significant impact on our bottom line.\n\n"
            "Great point, Maria. Let's make that a priority. John, can you "
            "prepare a detailed proposal by next Friday?\n\n"
            "Absolutely, I'll have that ready.\n\n"
            "Perfect. Let's also discuss the timeline for the new feature release. "
            "The engineering team estimates we can have the beta ready by mid-November.\n\n"
            "That works for our marketing timeline. We can coordinate the "
            "launch campaign accordingly.\n\n"
            "Excellent. To summarize, our action items are: John will prepare "
            "the retention proposal, marketing will draft the launch plan, "
            "and we'll reconvene next week to review progress.\n\n"
            "Thanks everyone for your time today. Meeting adjourned."
        )

        timestamps = [
            {
                "start_time": 0.0,
                "end_time": 8.5,
                "text": "Welcome everyone to today's quarterly planning meeting. I'm Sarah, and I'll be leading today's discussion.",
            },
            {
                "start_time": 8.5,
                "end_time": 22.0,
                "text": "First, let's review our Q3 results. We exceeded our revenue targets by 15%, which is a great achievement for the team. John, would you like to share the breakdown?",
            },
            {
                "start_time": 22.0,
                "end_time": 38.0,
                "text": "Thanks Sarah. So looking at the numbers, our enterprise segment grew by 22%, while the SMB segment showed steady 8% growth. The new product line we launched in August has been particularly successful.",
            },
            {
                "start_time": 38.0,
                "end_time": 52.0,
                "text": "That's excellent news. Now let's discuss our Q4 priorities. We need to focus on three main areas: customer retention, product improvements, and expanding into new markets.",
            },
            {
                "start_time": 52.0,
                "end_time": 68.0,
                "text": "I'd like to propose that we allocate additional resources to the customer success team. Based on our data, improving retention by just 5% would have a significant impact on our bottom line.",
            },
            {
                "start_time": 68.0,
                "end_time": 82.0,
                "text": "Great point, Maria. Let's make that a priority. John, can you prepare a detailed proposal by next Friday?",
            },
            {
                "start_time": 82.0,
                "end_time": 86.0,
                "text": "Absolutely, I'll have that ready.",
            },
            {
                "start_time": 86.0,
                "end_time": 98.0,
                "text": "Perfect. Let's also discuss the timeline for the new feature release. The engineering team estimates we can have the beta ready by mid-November.",
            },
            {
                "start_time": 98.0,
                "end_time": 108.0,
                "text": "That works for our marketing timeline. We can coordinate the launch campaign accordingly.",
            },
            {
                "start_time": 108.0,
                "end_time": 128.0,
                "text": "Excellent. To summarize, our action items are: John will prepare the retention proposal, marketing will draft the launch plan, and we'll reconvene next week to review progress.",
            },
            {
                "start_time": 128.0,
                "end_time": 135.0,
                "text": "Thanks everyone for your time today. Meeting adjourned.",
            },
        ]

        logger.info("Transcription complete")
        return {"text": full_text, "timestamps": timestamps}

    def cleanup(self) -> None:
        """Clean up temporary files created during transcription (WAV files, etc.)."""
        for temp_file in self._temp_files:
            try:
                if temp_file.exists():
                    temp_file.unlink()
                    logger.debug(f"Cleaned up temp file: {temp_file.name}")
            except OSError as e:
                logger.warning(f"Failed to clean up {temp_file}: {e}")
        self._temp_files.clear()
        self.model = None
        logger.info("Transcriber resources cleaned up")
