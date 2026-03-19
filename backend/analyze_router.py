"""
analyze_router.py
─────────────────
FastAPI router — POST /analyze

Register in main.py:
    from analyze_router import router as analyze_router
    app.include_router(analyze_router)
"""

from fastapi  import APIRouter
from pydantic import BaseModel
from typing   import Optional
from analyzer_engine import analyze_text, analyze_image, analyze_file

router = APIRouter()

VALID_LANGS  = {"english", "hindi", "marathi"}
VALID_MODES  = {"summary", "explain", "keypoints", "simplify", "critical"}


class AnalyzeRequest(BaseModel):
    # Input type
    content_type: str                          # "text" | "image" | "file"

    # Text
    text: Optional[str] = None

    # Image
    image_base64:     Optional[str] = None
    image_media_type: Optional[str] = "image/jpeg"

    # File
    file_base64: Optional[str] = None
    file_name:   Optional[str] = None

    # Analysis settings
    mode:   str = "summary"                    # summary | explain | keypoints | simplify | critical
    detail: int = 2                            # 1 brief | 2 balanced | 3 detailed

    # Language — optional.
    # • text : auto-detected from content; this overrides only when provided
    # • image: must be set by user (cannot detect language from pixels)
    # • file : auto-detected from extracted text; this overrides when provided
    lang: Optional[str] = None                # "english" | "hindi" | "marathi"


@router.post("/analyze")
async def analyze(data: AnalyzeRequest):
    mode   = data.mode   if data.mode   in VALID_MODES else "summary"
    detail = max(1, min(3, data.detail))
    lang   = data.lang   if data.lang   in VALID_LANGS else None   # None → auto-detect

    # ── Route by content type ─────────────────────────────────────────────────
    if data.content_type == "text":
        if not data.text or not data.text.strip():
            return {"error": "No text provided."}
        result = analyze_text(data.text.strip(), mode, detail, lang)

    elif data.content_type == "image":
        if not data.image_base64:
            return {"error": "No image data provided."}
        # For images, default to English if user didn't pick a language
        effective_lang = lang or "english"
        result = analyze_image(data.image_base64, data.image_media_type or "image/jpeg", mode, detail, effective_lang)

    elif data.content_type == "file":
        if not data.file_base64:
            return {"error": "No file data provided."}
        if not data.file_name:
            return {"error": "file_name is required to detect the file type."}
        result = analyze_file(data.file_base64, data.file_name, mode, detail, lang)

    else:
        return {"error": f"Unknown content_type '{data.content_type}'. Use: text, image, or file."}

    # ── Response ──────────────────────────────────────────────────────────────
    if result.get("error"):
        return {"error": result["error"]}

    return {
        "result": result["result"],
        "lang":   result["lang"],
        "mode":   mode,
    }