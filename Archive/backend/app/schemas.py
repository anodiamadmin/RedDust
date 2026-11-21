# schemas.py — Pydantic data contracts for the API
# These models define the shape of data coming IN (requests) and going OUT (responses).
# FastAPI uses these to automatically validate input and serialize output.
# Any request that doesn't match the schema is rejected with HTTP 422 before hitting business logic.

from typing import List, Optional
from pydantic import BaseModel, Field


class TrackRecommendation(BaseModel):
    """Represents a single music track recommendation returned to the frontend."""
    title: str          # Display name of the track
    youtube_url: str    # Link to the track on YouTube
    reason: str         # Human-readable explanation of why this track fits the user's mood


class ChatRequest(BaseModel):
    """Payload the frontend sends when the user submits a chat message."""
    user_message: str                   # The user's raw text input — required
    session_id: Optional[str] = None    # If None, a new session will be created server-side


class ChatResponse(BaseModel):
    """Full response returned to the frontend after processing the user's message."""
    reply: str                  # Syan's conversational response to the user
    followup_question: str      # A follow-up question to keep the conversation going
    session_id: str             # Session ID — frontend must echo this back in subsequent requests
    detected_mood: str = "neutral"          # Mood label detected from the conversation
    music_requested: bool = False           # True only if the user explicitly asked to play music
    tracks: List[TrackRecommendation] = Field(default_factory=list)
    # ^ default_factory=list is used instead of tracks=[] to avoid shared mutable default (Python footgun)
