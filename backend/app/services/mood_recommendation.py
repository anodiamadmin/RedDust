# services/mood_recommendation.py — Mood detection and music recommendation engine
#
# This module does two things:
#   1. Detects user mood — primarily from LLM output; keyword matching as fallback
#   2. Maps that mood to a curated list of music track recommendations
#
# Architecture: Dual-layer mood detection (graceful degradation pattern)
#   Layer 1 (Primary):   LLM-detected mood passed in from llm.py
#   Layer 2 (Fallback):  keyword-based Counter scan across full conversation history
# If the LLM returns a missing or invalid mood label, we fall back to Layer 2 automatically.
# This ensures mood detection never silently fails — the system always returns a valid mood.

from __future__ import annotations

import re
from collections import Counter
from typing import Optional, Sequence

from app.schemas import ChatResponse, TrackRecommendation


# --- Mood keyword map ---
# Each mood maps to a tuple of trigger words/phrases.
# Used by the fallback keyword detector to scan user messages and conversation history.
_MOOD_KEYWORDS = {
	"calm": ("calm", "peaceful", "relaxed", "rest", "breathe", "quiet"),
	"sad": ("sad", "down", "low", "cry", "depressed", "upset", "hurt"),
	"stressed": ("stress", "stressed", "pressure", "overwhelmed", "burned out", "burnt out"),
	"anxious": ("anxious", "anxiety", "worried", "nervous", "panic", "fearful"),
	"tired": ("tired", "sleepy", "exhausted", "drained", "fatigued", "worn out"),
	"lonely": ("lonely", "alone", "isolated", "miss", "missing", "disconnected"),
	"happy": ("happy", "good", "great", "excited", "joy", "uplifted", "fine"),
	"energetic": ("energetic", "active", "focused", "motivated", "pumped", "ready"),
	"reflective": ("think", "reflect", "reflective", "remember", "processing", "wondering"),
	"angry": ("angry", "frustrated", "mad", "annoyed", "irritated", "furious"),
}

# --- Mood-to-track map ---
# Each mood maps to a list of (title, youtube_url, reason) tuples.
# Currently uses placeholder URLs — replace with real curated links in production.
# Tracks are ordered by preference; recommend_tracks() slices the top N.
_MOOD_TRACKS = {
	"calm": [
		("Gentle Rain Radio", "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "Keeps the room soft and steady."),
		("Evening Lo-Fi Drift", "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "A low-pressure backdrop for recovery."),
		("Ambient Breath Session", "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "Helps slow the pace and settle attention."),
	],
	"sad": [
		("Warm Acoustic Comfort", "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "Soft support without overwhelming energy."),
		("Hopeful Piano Waves", "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "Keeps the mood gentle while lifting gradually."),
		("Quiet Company Mix", "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "Feels present without asking too much."),
	],
	"stressed": [
		("Reset Lo-Fi Flow", "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "Helps reduce mental clutter."),
		("Focus Break Beats", "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "Gives the mind a clean tempo to follow."),
		("Breathing Space Ambient", "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "Supports a short decompression pause."),
	],
	"anxious": [
		("Grounding Pulse", "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "Steady rhythm without sharp changes."),
		("Safe Harbor Instrumentals", "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "A predictable sound bed can feel stabilizing."),
		("Slow Drift Sessions", "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "Lets the energy settle before the next step."),
	],
	"tired": [
		("Soft Wake-Up Mix", "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "Gentle enough to avoid a hard edge."),
		("Low-Tempo Companion", "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "Keeps things calm while you recover."),
		("Sunrise Ambient Set", "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "Slowly adds a little lift."),
	],
	"lonely": [
		("Friendly Voice Radio", "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "Feels like company without pressure."),
		("Heartline Acoustic Session", "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "Warm and human, with room to breathe."),
		("Together Even When Apart", "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "Offers connection through steady sound."),
	],
	"happy": [
		("Bright Mood Booster", "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "Matches the uplift without overdoing it."),
		("Sunny Groove Set", "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "Keeps momentum moving forward."),
		("Joy Ride Tracks", "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "Adds a playful edge to a good moment."),
	],
	"energetic": [
		("Momentum Starter", "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "Supports action without losing control."),
		("Pulse Drive Mix", "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "Keeps motivation high and focused."),
		("Active Flow Radio", "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "Good for getting things done."),
	],
	"reflective": [
		("Late Night Thoughts", "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "Leaves space for meaning-making."),
		("Minimal Piano Journal", "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "Helps keep the mind clear while processing."),
		("Soft Focus Instrumentals", "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "A quiet backdrop for self-check-in."),
	],
	"angry": [
		("Cooldown Bassline", "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "Helps discharge tension without escalation."),
		("Slow Burn Reset", "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "Lets intensity settle into a steadier rhythm."),
		("Clear Head Tracks", "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "Creates a buffer before the next response."),
	],
	"neutral": [
		("Balanced Flow Radio", "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "A safe default when mood is still unclear."),
		("Everyday Companion Mix", "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "Works across most low-stakes moments."),
		("Open Space Instrumentals", "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "Leaves room for the conversation to guide us."),
	],
}

# All valid mood labels — used to validate the LLM's detected_mood before trusting it
_VALID_MOODS = set(_MOOD_KEYWORDS.keys()) | {"neutral"}


def _normalize_text(text: str) -> str:
	"""Lowercases and collapses whitespace for consistent keyword matching."""
	return re.sub(r"\s+", " ", text.lower()).strip()


def detect_mood_from_keywords(user_message: str, history: Optional[Sequence[str]] = None) -> str:
	"""
	Fallback mood detector — used only when the LLM doesn't return a valid detected_mood.

	Scans the full conversation history + current message for known mood keywords.
	Uses Counter to score each mood by keyword hit count and returns the highest-scoring one.
	Returns "neutral" if no keywords match.
	"""
	# Combine full history + current message into one text blob for scanning
	combined_text = " ".join([*(history or []), user_message])
	normalized_text = _normalize_text(combined_text)

	scores = Counter()
	for mood, keywords in _MOOD_KEYWORDS.items():
		for keyword in keywords:
			if keyword in normalized_text:
				scores[mood] += 1

	if not scores:
		return "neutral"

	# Return the mood with the highest keyword hit count
	return scores.most_common(1)[0][0]


def recommend_tracks(mood: str, limit: int = 3) -> list[TrackRecommendation]:
	"""
	Returns the top `limit` track recommendations for the given mood.
	Falls back to "neutral" tracks if an unrecognised mood is passed.
	"""
	track_rows = _MOOD_TRACKS.get(mood, _MOOD_TRACKS["neutral"])
	return [
		TrackRecommendation(title=title, youtube_url=youtube_url, reason=reason)
		for title, youtube_url, reason in track_rows[:limit]
	]


def build_syan_response(
	*,
	reply: str,
	followup_question: str,
	session_id: str,
	user_message: str,
	history: Optional[Sequence[str]] = None,
	detected_mood: Optional[str] = None,
	music_requested: bool = False,
) -> ChatResponse:
	"""
	Assembles the final ChatResponse object.

	Mood resolution priority:
	  1. Use detected_mood from LLM if it's a valid label (in _VALID_MOODS)
	  2. Fall back to keyword-based detection if LLM mood is missing or invalid

	This ensures we never return an unrecognised mood to the frontend.
	"""
	if detected_mood and detected_mood in _VALID_MOODS:
		mood = detected_mood         # Trust the LLM — it has full conversation context
	else:
		mood = detect_mood_from_keywords(user_message, history)   # Deterministic fallback

	return ChatResponse(
		reply=reply,
		followup_question=followup_question,
		session_id=session_id,
		detected_mood=mood,
		music_requested=music_requested,
		tracks=recommend_tracks(mood),   # Always return 3 tracks for the detected mood
	)
