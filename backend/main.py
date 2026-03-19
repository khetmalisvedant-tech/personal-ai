"""
main.py
───────
FastAPI entry point for Personal AI Tutor backend.

Run with:
    python -m uvicorn main:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes         import router as main_router      # /ask  /voices  /voice-preview
from analyze_router import router as analyze_router   # /analyze

app = FastAPI(
    title="Personal AI Tutor",
    version="2.0.0",
    description="AI Tutor with Voice, Multilingual support, and Document Analyzer",
)

# ── CORS — allow frontend (React dev server) to talk to backend ───────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # tighten this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register routers ──────────────────────────────────────────────────────────
app.include_router(main_router)      # POST /ask
                                     # GET  /voices
                                     # POST /voice-preview

app.include_router(analyze_router)   # POST /analyze


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/")
async def root():
    return {
        "status":  "running",
        "version": "2.0.0",
        "routes": [
            "POST /ask",
            "GET  /voices",
            "POST /voice-preview",
            "POST /analyze",
        ],
    }