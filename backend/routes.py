"""
routes.py
─────────
FastAPI router for:
  POST /ask              — tutor Q&A  (now accepts voice settings)
  GET  /voices           — returns voice catalog for frontend dropdowns
"""

from fastapi   import APIRouter
from pydantic  import BaseModel
from typing    import Optional

from core          import process_query
from murf_service  import get_voice_catalog

router = APIRouter()


# ── Request schema ─────────────────────────────────────────────────────────────
class QuestionRequest(BaseModel):
    question:  str

    # Voice settings — all optional, fall back to defaults if not sent
    voice_id:  Optional[str] = None    # Murf voiceId or cloned voice ID
    pitch:     Optional[int] = 0       # -50 to +50
    rate:      Optional[int] = 0       # -50 (slow) to +50 (fast)
    emphasis:  Optional[str] = "none"  # none | strong | moderate | reduced


# ── Endpoints ──────────────────────────────────────────────────────────────────
@router.post("/ask")
async def ask(data: QuestionRequest):
    question = data.question.strip()
    if not question:
        return {"error": "No question provided"}

    return process_query(
        question  = question,
        voice_id  = data.voice_id,
        pitch     = data.pitch  or 0,
        rate      = data.rate   or 0,
        emphasis  = data.emphasis or "none",
    )


@router.get("/voices")
async def voices():
    """Return available Murf voices grouped by language."""
    return {"voices": get_voice_catalog()}


# ── Voice preview request ──────────────────────────────────────────────────────
class VoicePreviewRequest(BaseModel):
    text:      str
    lang:      Optional[str] = "english"
    voice_id:  Optional[str] = None
    pitch:     Optional[int] = 0
    rate:      Optional[int] = 0
    emphasis:  Optional[str] = "none"


@router.post("/voice-preview")
async def voice_preview(data: VoicePreviewRequest):
    """
    Real-time voice preview — generates audio for any text
    with the given voice settings immediately.
    """
    from murf_service import generate_voice

    text = data.text.strip()[:300]
    if not text:
        return {"error": "No text provided for preview"}

    result = generate_voice(
        text     = text,
        lang     = data.lang or "english",
        voice_id = data.voice_id,
        pitch    = data.pitch  or 0,
        rate     = data.rate   or 0,
        emphasis = data.emphasis or "none",
    )

    if result.get("error"):
        return {"error": result["error"]}

    return {
        "audio_url": result.get("audio_url"),
        "audio_b64": result.get("audio_b64"),
        "provider":  result.get("provider"),
    }