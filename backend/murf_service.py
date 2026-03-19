"""
murf_service.py
───────────────
Enhanced voice service:
  • Fetches REAL voice IDs live from Murf's /v1/speech/voices endpoint
  • Caches them so the API is only called once per server session
  • Safe hardcoded fallback catalog if Murf API is unreachable
  • gTTS fallback if no MURF_API_KEY is set
"""

import os
import io
import base64
import requests

MURF_GENERATE_URL = "https://api.murf.ai/v1/speech/generate"
MURF_VOICES_URL   = "https://api.murf.ai/v1/speech/voices"

# ── Only 100% confirmed valid Murf voice IDs used as safe defaults ────────────
SAFE_DEFAULTS = {
    "english": "en-US-natalie",
    "hindi":   "hi-IN-amit",
    "marathi": "hi-IN-amit",
}

# ── Hardcoded fallback catalog (used only if Murf API is unreachable) ─────────
# These are the minimal known-valid IDs from Murf's public docs
FALLBACK_CATALOG = {
    "english": [
        {"id": "en-US-natalie", "name": "Natalie (US, Female)"},
        {"id": "en-US-ken",     "name": "Ken (US, Male)"},
    ],
    "hindi": [
        {"id": "hi-IN-amit",    "name": "Amit (Male)"},
    ],
    "marathi": [
        {"id": "hi-IN-amit",    "name": "Amit (Male)"},
    ],
}

# ── In-memory cache — populated on first call to get_voice_catalog() ──────────
_catalog_cache: dict | None = None


# ── Fetch real voices from Murf API ──────────────────────────────────────────
def _fetch_murf_voices() -> dict:
    """
    Calls Murf GET /v1/speech/voices and returns a catalog dict:
      { "english": [{id, name}, ...], "hindi": [...], "marathi": [...] }
    Falls back to FALLBACK_CATALOG on any error.
    """
    api_key = os.getenv("MURF_API_KEY")
    if not api_key:
        return FALLBACK_CATALOG

    try:
        resp = requests.get(
            MURF_VOICES_URL,
            headers={"api-key": api_key, "Content-Type": "application/json"},
            timeout=10,
        )
        if resp.status_code != 200:
            print(f"⚠️ Murf /voices returned {resp.status_code} — using fallback catalog")
            return FALLBACK_CATALOG

        data   = resp.json()
        voices = data if isinstance(data, list) else data.get("voices", [])

        catalog = {"english": [], "hindi": [], "marathi": []}

        for v in voices:
            vid    = v.get("voiceId") or v.get("voice_id") or v.get("id", "")
            vname  = v.get("displayName") or v.get("name") or vid
            locale = (v.get("locale") or v.get("language") or "").lower()

            entry = {"id": vid, "name": vname}

            if locale.startswith("hi"):
                catalog["hindi"].append(entry)
                catalog["marathi"].append(entry)   # reuse Hindi voices for Marathi
            elif locale.startswith("en"):
                catalog["english"].append(entry)

        # If any bucket is empty fall back to the hardcoded list for that lang
        for lang in catalog:
            if not catalog[lang]:
                catalog[lang] = FALLBACK_CATALOG[lang]

        print(f"✅ Loaded {sum(len(v) for v in catalog.values())} voices from Murf API")
        return catalog

    except Exception as e:
        print(f"⚠️ Could not fetch Murf voices: {e} — using fallback catalog")
        return FALLBACK_CATALOG


def get_voice_catalog() -> dict:
    """Return cached voice catalog, fetching from Murf API on first call."""
    global _catalog_cache
    if _catalog_cache is None:
        _catalog_cache = _fetch_murf_voices()
    return _catalog_cache


def _get_default_voice(lang: str) -> str:
    """Pick the first available voice for a language from the live catalog."""
    catalog = get_voice_catalog()
    voices  = catalog.get(lang) or catalog.get("english") or []
    if voices:
        return voices[0]["id"]
    return SAFE_DEFAULTS.get(lang, "en-US-natalie")


# ── Main public function ──────────────────────────────────────────────────────
def generate_voice(
    text:      str,
    lang:      str = "english",
    voice_id:  str = None,
    pitch:     int = 0,
    rate:      int = 0,
    emphasis:  str = "none",
) -> dict:
    api_key = os.getenv("MURF_API_KEY")
    if api_key:
        return _generate_murf(text, lang, voice_id, pitch, rate, emphasis, api_key)
    else:
        print("⚠️  MURF_API_KEY not set — falling back to gTTS")
        return _generate_gtts(text, lang)


# ── Murf TTS ──────────────────────────────────────────────────────────────────
def _generate_murf(text, lang, voice_id, pitch, rate, emphasis, api_key) -> dict:
    # Use provided voice_id, or pick first valid one from live catalog
    chosen_voice = voice_id if voice_id else _get_default_voice(lang)

    pitch    = max(-50, min(50, int(pitch or 0)))
    rate     = max(-50, min(50, int(rate  or 0)))
    emphasis = emphasis if emphasis in ("none","strong","moderate","reduced") else "none"

    payload = {
        "text":       text.strip()[:500],
        "voiceId":    chosen_voice,
        "format":     "MP3",
        "pitch":      pitch,
        "rate":       rate,
        "sampleRate": 48000,
    }
    if emphasis != "none":
        payload["emphasis"] = emphasis

    headers = {"api-key": api_key, "Content-Type": "application/json"}

    try:
        print(f"🔊 Murf [{lang} → {chosen_voice}] pitch={pitch} rate={rate} emphasis={emphasis}")
        print(f"   Text: {text[:80]}")

        response = requests.post(MURF_GENERATE_URL, json=payload, headers=headers, timeout=30)
        print(f"   Status: {response.status_code}")

        if response.status_code != 200:
            err = response.text
            print("❌ Murf error:", err)

            # If the voice_id is invalid, reset cache and retry with safe default
            if "Invalid voice_id" in err and voice_id:
                print("🔄 Invalid voice_id — retrying with safe default...")
                safe = SAFE_DEFAULTS.get(lang, "en-US-natalie")
                return _generate_murf(text, lang, safe, pitch, rate, emphasis, api_key)

            # If even safe default fails, fall back to gTTS
            print("🔄 Falling back to gTTS...")
            return _generate_gtts(text, lang)

        data      = response.json()
        audio_url = data.get("audioFile")

        if not audio_url:
            print("❌ No audioFile in Murf response:", data)
            return _generate_gtts(text, lang)

        print("✅ Murf audio:", audio_url)
        return {"audio_url": audio_url, "audio_b64": None, "provider": "murf", "error": None}

    except requests.Timeout:
        print("⏱ Murf timed out — falling back to gTTS")
        return _generate_gtts(text, lang)
    except Exception as e:
        print("❌ Murf exception:", e)
        return _generate_gtts(text, lang)


# ── gTTS fallback ─────────────────────────────────────────────────────────────
def _generate_gtts(text: str, lang: str) -> dict:
    try:
        from gtts import gTTS
    except ImportError:
        return {
            "audio_url": None, "audio_b64": None, "provider": "gtts",
            "error": "gTTS not installed. Run: pip install gtts",
        }

    lang_code = {"english":"en", "hindi":"hi", "marathi":"mr"}.get(lang, "en")
    try:
        tts = gTTS(text=text[:500], lang=lang_code, slow=False)
        buf = io.BytesIO()
        tts.write_to_fp(buf)
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        print(f"✅ gTTS fallback generated ({lang_code})")
        return {"audio_url": None, "audio_b64": b64, "provider": "gtts", "error": None}
    except Exception as e:
        print("❌ gTTS error:", e)
        return {"audio_url": None, "audio_b64": None, "provider": "gtts", "error": str(e)}