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

from app.schemas import ChatResponse


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
		tracks=[],    # Music handled via Gemini Live function calls — not returned in the HTTP chat flow
	)
