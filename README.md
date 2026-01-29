# Transcription Tool

A FastAPI + HTMX fullstack application for video transcription with summarization and meeting minutes extraction.

## Features

- **Video Upload**: Drag and drop or browse to upload video files
- **Transcription**: Get instant transcription with optional timestamps
- **Summarization**: AI-powered text summarization
- **Meeting Minutes**: Extract structured meeting notes including attendees, action items, and decisions
- **Copy & Download**: Copy transcription to clipboard or download as text file

## Quick Start

```bash
# Install dependencies
uv sync

# Run development server
uv run uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000 in your browser.

## Tech Stack

- **Backend**: FastAPI, Python 3.11+
- **Frontend**: HTMX, vanilla JavaScript
- **Styling**: Custom CSS with dark theme
- **Package Manager**: uv

## Project Structure

```
transcription_tool/
├── app/
│   ├── core/          # Config and logging
│   ├── models/        # Pydantic schemas
│   ├── routers/       # API endpoints
│   ├── services/      # Business logic
│   ├── static/        # CSS and JS
│   └── templates/     # HTML templates
└── uploads/           # Uploaded videos
```

## Environment Variables

- `ENVIRONMENT`: `development` or `production` (default: development)
- `HOST`: Server host (default: 0.0.0.0)
- `PORT`: Server port (default: 8000)
