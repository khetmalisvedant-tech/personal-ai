import requests
import json
from memory import get_history

OLLAMA_URL = "http://localhost:11434/api/generate"


def detect_language(text: str):
    """
    Detects language from input text.
    Returns: 'hindi', 'marathi', or 'english'

    Since both Hindi and Marathi share Devanagari script,
    we use keyword heuristics to distinguish them.
    """
    marathi_keywords = [
        "आहे", "आणि", "काय", "कसे", "मला", "तुम्ही", "आपण",
        "सांगा", "करा", "हे", "ते", "नाही", "होय", "मराठी",
        "त्याचा", "त्याची", "आम्ही", "तुमचा", "कोण", "कुठे"
    ]

    hindi_keywords = [
        "है", "और", "क्या", "कैसे", "मुझे", "आप", "हम",
        "बताओ", "करो", "यह", "वह", "नहीं", "हाँ", "हिंदी",
        "उसका", "उसकी", "तुम्हारा", "कौन", "कहाँ", "मैं"
    ]

    has_devanagari = False
    for ch in text:
        if "\u0900" <= ch <= "\u097F":
            has_devanagari = True
            break

    if not has_devanagari:
        return "english"

    for word in marathi_keywords:
        if word in text:
            return "marathi"

    for word in hindi_keywords:
        if word in text:
            return "hindi"

    # Default fallback for unrecognised Devanagari: Hindi
    return "hindi"


def generate_tutor_response(user_input: str):
    history = get_history()

    history_text = ""
    for msg in history:
        history_text += f"{msg['role']}: {msg['content']}\n"

    lang = detect_language(user_input)

    # Explicit, unambiguous language instruction for LLaMA3
    if lang == "marathi":
        language_instruction = (
            "STRICT RULE: You MUST respond ONLY in Marathi language. "
            "Do NOT use Hindi. Do NOT use English. "
            "Every word in explanation, summary, and quiz must be in Marathi."
        )
    elif lang == "hindi":
        language_instruction = (
            "STRICT RULE: You MUST respond ONLY in Hindi language. "
            "Do NOT use Marathi. Do NOT use English. "
            "Every word in explanation, summary, and quiz must be in Hindi."
        )
    else:
        language_instruction = (
            "STRICT RULE: You MUST respond ONLY in English language. "
            "Do NOT use Hindi or Marathi. "
            "Every word in explanation, summary, and quiz must be in English."
        )

    prompt = f"""You are a helpful AI tutor for students.

Conversation so far:
{history_text}

{language_instruction}

Return ONLY valid JSON. No text outside JSON. No markdown backticks.

Format:
{{
  "explanation": "clear explanation in the REQUIRED language",
  "summary": "one-sentence summary in the REQUIRED language (max 100 words)",
  "quiz": [
    "Question 1 in the REQUIRED language?",
    "Question 2 in the REQUIRED language?",
    "Question 3 in the REQUIRED language?"
  ]
}}

User Question ({lang.upper()}):
{user_input}
"""

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": "llama3",
                "prompt": prompt,
                "stream": False
            },
            timeout=60
        )

        data = response.json()
        output = data.get("response", "").strip()

        # Strip markdown fences if model wraps output in ```json
        if output.startswith("```"):
            output = output.split("```")[1]
            if output.startswith("json"):
                output = output[4:]
            output = output.strip()

        try:
            parsed = json.loads(output)
            if "quiz" not in parsed or not isinstance(parsed["quiz"], list):
                parsed["quiz"] = []
            parsed["lang"] = lang  # pass detected lang to frontend
        except Exception:
            parsed = {
                "explanation": output,
                "summary": output[:200],
                "quiz": [],
                "lang": lang
            }

        return parsed

    except Exception as e:
        print("Engine Error:", e)
        return {
            "explanation": "Error generating response. Please try again.",
            "summary": "An error occurred.",
            "quiz": [],
            "lang": "english"
        }
