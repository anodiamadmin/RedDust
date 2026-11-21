# services/gemini_tools.py — Gemini Live tool (function) declarations for RedDust
#
# Responsibility:
#   Define all function declarations sent to Gemini Live at session start.
#   Gemini reads these once and uses them to decide when and how to call each
#   function during a conversation.
#
# Why a dedicated file?
#   - Single source of truth for all tool schemas — changes here automatically
#     propagate to every session without touching audio_relay.py
#   - Keeps audio_relay.py clean — it just imports SYAN_TOOLS and passes it to
#     the Gemini Live session config
#   - New functions (e.g. log_mood, set_reminder) can be added here without
#     touching any other file
#
# How Gemini Live uses these:
#   1. You pass SYAN_TOOLS into LiveConnectConfig(tools=[...]) at session start
#   2. Gemini reads the declarations and knows what functions exist
#   3. During conversation, Gemini decides when to call a function and fills in
#      the parameters based on the description fields and conversation context
#   4. Your function_dispatcher.py receives the call and routes it to the handler
#
# Registered functions (must match handlers in function_dispatcher.py):
#   - fetch_user_context          → user_context.py  (Step 15)
#   - get_music_recommendation    → music.py          (Step 16)
#   - retrieve_anodiam_knowledge  → knowledge.py      (Step 17)

from google.genai import types


# ---------------------------------------------------------------------------
# fetch_user_context
# ---------------------------------------------------------------------------
# Called once at session start so Syan knows who it's talking to.
# Fetches profile, preferences, soul score summary, and conversation history.
# Gemini calls this proactively at the beginning of every session.
# ---------------------------------------------------------------------------
_FETCH_USER_CONTEXT = types.FunctionDeclaration(
    name="fetch_user_context",
    description=(
        "Fetch the user's profile, music preferences, soul score summary, and recent "
        "conversation history from the database. Call this at the very start of every "
        "session so Syan can personalise the conversation from the first message. "
        "Do not wait for the user to ask — call it immediately when the session begins."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={},          # No parameters — user_id is injected server-side
        required=[],
    ),
)


# ---------------------------------------------------------------------------
# get_music_recommendation
# ---------------------------------------------------------------------------
# Called when the user wants music or when music would support their goal.
# Gemini fills in the parameters from conversation context — the richer the
# conversation, the more signals Gemini can pass for better personalisation.
# ---------------------------------------------------------------------------
_GET_MUSIC_RECOMMENDATION = types.FunctionDeclaration(
    name="get_music_recommendation",
    description=(
        "Recommend personalised music tracks based on the user's current emotional state, "
        "desired emotional outcome, activity, energy level, and time of day. "
        "Call this when the user asks for music, mentions how they're feeling and music "
        "would help, or when music would support their current goal or activity. "
        "Fill in as many parameters as the conversation context allows — more signals "
        "produce better recommendations."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "mood_hint": types.Schema(
                type=types.Type.STRING,
                description=(
                    "The user's current detected emotional state. "
                    "Examples: anxious, sad, happy, stressed, tired, angry, "
                    "neutral, motivated, focused, lonely."
                ),
            ),
            "desired_mood": types.Schema(
                type=types.Type.STRING,
                description=(
                    "The emotional state the user wants to reach — may differ from mood_hint. "
                    "For example, the user is tired but wants to feel motivated. "
                    "Examples: relaxed, energized, focused, uplifted, calm, sleepy."
                ),
            ),
            "activity": types.Schema(
                type=types.Type.STRING,
                description=(
                    "What the user is doing or about to do. "
                    "Examples: study, sleep, workout, commute, relax, meditate, cook, work."
                ),
            ),
            "energy_level": types.Schema(
                type=types.Type.STRING,
                enum=["low", "medium", "high"],
                description=(
                    "The user's current energy level, independent of mood. "
                    "A user can be happy but low energy, or stressed but high energy."
                ),
            ),
            "time_of_day": types.Schema(
                type=types.Type.STRING,
                enum=["morning", "afternoon", "evening", "night"],
                description=(
                    "The current part of the day. Used to match music energy to "
                    "natural daily rhythms — e.g. avoid high-energy tracks at night."
                ),
            ),
            "session_goal": types.Schema(
                type=types.Type.STRING,
                description=(
                    "What the user is trying to achieve this session — broader than activity. "
                    "Captures the intended outcome of the listening experience, which shapes "
                    "the arc of the music journey, not just the first track. "
                    "Examples: 'focus for 3 hours', 'wind down before sleep', "
                    "'recover from an argument', 'get pumped before a presentation'."
                ),
            ),
        },
        required=["mood_hint"],
    ),
)


# ---------------------------------------------------------------------------
# retrieve_anodiam_knowledge
# ---------------------------------------------------------------------------
# Called when Syan needs grounded knowledge to answer a wellbeing question.
# Queries the RAG pipeline (Anodiam knowledge base) for research-backed answers.
# ---------------------------------------------------------------------------
_RETRIEVE_ANODIAM_KNOWLEDGE = types.FunctionDeclaration(
    name="retrieve_anodiam_knowledge",
    description=(
        "Retrieve grounded, research-backed knowledge from the Anodiam knowledge base "
        "to answer wellbeing, mental health, or soul score questions. "
        "Call this when the user asks about wellbeing topics, emotional science, "
        "or the meaning of their soul score dimensions — do not answer from memory alone."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "query": types.Schema(
                type=types.Type.STRING,
                description=(
                    "The topic or question to look up in the knowledge base. "
                    "Be specific — e.g. 'how does sleep affect emotional regulation' "
                    "rather than just 'sleep'."
                ),
            ),
            "domain": types.Schema(
                type=types.Type.STRING,
                enum=["research", "wisdom", "soul_score"],
                description=(
                    "The knowledge domain to search. "
                    "'research' for scientific studies, "
                    "'wisdom' for philosophical or motivational content, "
                    "'soul_score' for dimension definitions and scoring explanations."
                ),
            ),
        },
        required=["query"],
    ),
)


# ---------------------------------------------------------------------------
# SYAN_TOOLS — import this in audio_relay.py and pass to LiveConnectConfig
#
# Usage in audio_relay.py:
#   from app.services.gemini_tools import SYAN_TOOLS
#   config = LiveConnectConfig(tools=SYAN_TOOLS, ...)
# ---------------------------------------------------------------------------
SYAN_TOOLS = [
    types.Tool(function_declarations=[
        _FETCH_USER_CONTEXT,
        _GET_MUSIC_RECOMMENDATION,
        _RETRIEVE_ANODIAM_KNOWLEDGE,
    ])
]
