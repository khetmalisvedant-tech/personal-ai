"""
core.py
───────
Orchestrates: AI engine → voice generation → response assembly.
Now passes voice_settings (voice_id, pitch, rate, emphasis) from the
request all the way through to murf_service.
"""

from engine       import generate_tutor_response
from murf_service import generate_voice
from memory       import add_message, get_history

DEFAULT_SESSION = "default"


def process_query(
    question:      str,
    voice_id:      str = None,
    pitch:         int = 0,
    rate:          int = 0,
    emphasis:      str = "none",
):
    print("QUESTION RECEIVED:", question)

    add_message(DEFAULT_SESSION, "user", question)

    ai_output = generate_tutor_response(question, DEFAULT_SESSION)

    explanation = ai_output.get("explanation", "")
    summary     = ai_output.get("summary",     "")
    quiz        = ai_output.get("quiz",        [])
    lang        = ai_output.get("lang",        "english")

    if not explanation.strip():
        return {"error": "AI failed to generate a response. Please try again."}

    add_message(DEFAULT_SESSION, "assistant", explanation)

    # Use summary for audio if available, else first 300 chars of explanation
    voice_text = summary if summary.strip() else explanation[:300]

    # ── Generate voice with all settings ─────────────────────────────────────
    voice_result = generate_voice(
        text      = voice_text,
        lang      = lang,
        voice_id  = voice_id or None,
        pitch     = pitch,
        rate      = rate,
        emphasis  = emphasis,
    )

    result = {
        "explanation":  explanation,
        "summary":      summary,
        "quiz":         quiz,
        "lang":         lang,
        "voice_provider": voice_result.get("provider", "murf"),
    }

    # Audio can come as a URL (Murf) or base64 (gTTS fallback)
    if voice_result.get("audio_url"):
        result["audio"]      = voice_result["audio_url"]
        result["audio_type"] = "url"

    elif voice_result.get("audio_b64"):
        result["audio"]      = voice_result["audio_b64"]
        result["audio_type"] = "base64"

    else:
        result["audio"]       = None
        result["audio_type"]  = None
        result["audio_error"] = voice_result.get("error", "Audio generation failed.")

    return result