from engine import generate_tutor_response
from murf_service import generate_voice
from memory import add_message


def process_query(question: str):
    print("QUESTION RECEIVED:", question)

    add_message("user", question)

    ai_output = generate_tutor_response(question)

    explanation = ai_output.get("explanation", "")
    summary = ai_output.get("summary", "")
    quiz = ai_output.get("quiz", [])
    lang = ai_output.get("lang", "english")   # ← pass detected language

    if not explanation.strip():
        return {"error": "AI failed to generate a response. Please try again."}

    add_message("assistant", explanation)

    voice_text = summary if summary.strip() else explanation[:300]

    audio_url = generate_voice(voice_text, lang)   # ← pass lang to Murf

    result = {
        "explanation": explanation,
        "summary": summary,
        "quiz": quiz,
        "lang": lang,
    }

    if audio_url:
        result["audio"] = audio_url
    else:
        result["audio"] = None
        result["audio_error"] = "Audio generation failed. Check your Murf API key."

    return result
