import json
from typing import Iterable, cast  # 1. Import cast and Iterable
from groq import Groq
from groq.types.chat import ChatCompletionMessageParam
from config import GROQ_API_KEY, MODEL_NAME

client = Groq(api_key=GROQ_API_KEY)


def build_prompt(row, columns, situation, meanings, questions):
    """Constructs the persona-specific prompt."""
    persona_context = "\n".join([f"{col}: {row[col]}" for col in columns])

    return f"""
    {situation}

    === YOUR SPECIFIC PERSONA DETAILS ===
    {persona_context}

    === SCORING SYSTEM ===
    {meanings}

    === THE SURVEY QUESTIONS ===
    {questions}

    === OUTPUT REQUIREMENTS ===
    You must respond in strictly valid JSON format. 
    Provide ONLY the numerical score (1 to 5) for each question based on your persona.
    Do NOT include text explanations. Do NOT include markdown blocks like ```json.

    Your JSON must be formatted exactly like this:
    {{
        "Q1": 4,
        "Q2": 2,
        "Q3": 5,
        "Q4": 3,
        "Q5": 4,
        "Q6": 5,
        "Q7": 2,
        "Q8": 4,
        "Q9": 5,
        "Q10": 4,
        "Q11": 3,
        "Q12": 5,
        "Q13": 4,
        "Q14": 2,
        "Q15": 5
    }}
    """


def get_survey_response(prompt, persona_name):
    """Sends the prompt to Groq and returns the JSON dictionary."""

    # 2. Use 'cast' to force the IDE to accept these dictionaries as Groq's exact required type
    messages = cast(Iterable[ChatCompletionMessageParam], [
        {
            "role": "system",
            "content": "You are an AI participating in a survey. Output strictly valid JSON containing only numerical scores."
        },
        {
            "role": "user",
            "content": prompt
        }
    ])

    try:
        chat_completion = client.chat.completions.create(
            messages=messages,
            model=MODEL_NAME,
            temperature=0.3,
            response_format={"type": "json_object"} # type: ignore
        )

        response_content = chat_completion.choices[0].message.content
        return json.loads(response_content)

    except Exception as e:
        print(f" [!] Error processing {persona_name}: {e}")
        return {}