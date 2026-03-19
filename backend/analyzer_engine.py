"""
analyzer_engine.py  (v3 — streaming)
──────────────────────────────────────
• stream_analyze()  → generator that yields text chunks as Ollama produces them
• analyze_text/image/file() kept for non-streaming callers (fallback)

Text & files  → llama3.2
Images        → llava:13b

PDF support   → pip install pypdf
"""

import base64
import io
import json
import requests
from engine import detect_language

OLLAMA_URL   = "http://localhost:11434/api/generate"
TEXT_MODEL   = "llama3.2"
VISION_MODEL = "llava:13b"


# ── Strip JSON wrapper if model misbehaves ────────────────────────────────────
def _strip_json_wrapper(text: str) -> str:
    """
    If the model wraps its answer in JSON like:
      {"result":"actual answer","lang":"english","mode":"summary"}
    extract just the 'result' value.
    Also strips markdown code fences like ```json ... ```
    """
    t = text.strip()

    # Strip markdown code fences
    if t.startswith("```"):
        lines = t.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        t = "\n".join(lines).strip()

    # Try JSON parse — extract "result" key if present
    if t.startswith("{"):
        try:
            parsed = json.loads(t)
            if isinstance(parsed, dict) and "result" in parsed:
                return str(parsed["result"]).strip()
        except json.JSONDecodeError:
            # Partial JSON (still streaming) — check if it starts with {"result":"
            if t.startswith('{"result":"') or t.startswith('{ "result": "'):
                # Extract what's already streamed after the key
                start = t.find('"result"')
                if start != -1:
                    colon = t.find(":", start)
                    if colon != -1:
                        # Find opening quote of value
                        q = t.find('"', colon + 1)
                        if q != -1:
                            return t[q + 1:].rstrip('",}').strip()

    return t

# ── Per-mode token budgets — Brief needs far fewer tokens than Critical ────────
TOKEN_BUDGET = {
    # (brief, balanced, detailed)
    "summary":   (120, 250, 450),
    "explain":   (150, 300, 550),
    "keypoints": (100, 200, 350),
    "simplify":  (120, 240, 400),
    "critical":  (200, 380, 650),
}

# ── Mode prompts ──────────────────────────────────────────────────────────────
MODE_PROMPTS = {
    "summary":
        "Write a clear, accurate SUMMARY. Capture main ideas and key details.",
    "explain":
        "Provide a clear EXPLANATION. Break down concepts, clarify meaning and relationships.",
    "keypoints":
        "Extract KEY POINTS as a clean numbered list. Most important ideas only.",
    "simplify":
        "SIMPLIFY so a 10-year-old understands. Use plain language and analogies. No jargon.",
    "critical":
        "Provide a CRITICAL ANALYSIS covering strengths, weaknesses, assumptions, and implications.",
}

DETAIL_INSTRUCTIONS = {
    1: "Be very concise — 3 to 5 sentences maximum.",
    2: "Be moderately detailed — cover key points without over-explaining.",
    3: "Be thorough and comprehensive. Depth and nuance are expected.",
}

LANG_RULES = {
    "marathi": "Reply ONLY in Marathi. Do NOT use Hindi or English.",
    "hindi":   "Reply ONLY in Hindi. Do NOT use Marathi or English.",
    "english": "Reply ONLY in English. Do NOT use Hindi or Marathi.",
}


# ── Prompt builder ────────────────────────────────────────────────────────────
def _build_prompt(mode: str, detail: int, content: str, lang: str = "english") -> str:
    return (
        f"You are an expert AI analyst. {LANG_RULES.get(lang, LANG_RULES['english'])}\n"
        f"{MODE_PROMPTS.get(mode, MODE_PROMPTS['summary'])} "
        f"{DETAIL_INSTRUCTIONS.get(detail, DETAIL_INSTRUCTIONS[2])}\n\n"
        f"STRICT OUTPUT RULES — violating any rule is not allowed:\n"
        f"- Output ONLY the analysis as plain readable text.\n"
        f"- Do NOT wrap output in JSON, markdown code blocks, or any brackets.\n"
        f"- Do NOT start with 'Here is', 'Sure', 'The following', 'Based on' or any preamble.\n"
        f"- Do NOT include keys like 'result:', 'lang:', 'mode:' or curly braces.\n"
        f"- Do NOT add any closing remarks like 'I hope this helps'.\n"
        f"- Start your response directly with the analysis content.\n\n"
        f"CONTENT TO ANALYZE:\n{content}"
    )


def _get_tokens(mode: str, detail: int) -> int:
    budget = TOKEN_BUDGET.get(mode, (200, 350, 600))
    return budget[detail - 1]


# ════════════════════════════════════════════════════════════════════════════
# STREAMING  (primary path)
# ════════════════════════════════════════════════════════════════════════════
def stream_analyze(
    content_type: str,
    mode:         str,
    detail:       int,
    # text
    text:             str  = None,
    # image
    image_base64:     str  = None,
    image_media_type: str  = "image/jpeg",
    # file
    file_base64:      str  = None,
    file_name:        str  = None,
    # language override
    lang:             str  = None,
):
    """
    Generator that yields plain-text chunks as Ollama streams them.
    Yields error strings prefixed with '__ERROR__:' on failure.
    First chunk is always '__LANG__:<lang>\n' so the frontend knows the language.
    """
    # ── Resolve content + language ────────────────────────────────────────────
    prompt_text, detected_lang, images = _resolve_content(
        content_type, text, image_base64, image_media_type,
        file_base64, file_name, lang
    )
    if prompt_text.startswith("__ERROR__:"):
        yield prompt_text
        return

    yield f"__LANG__:{detected_lang}\n"

    model  = VISION_MODEL if content_type == "image" else TEXT_MODEL
    prompt = _build_prompt(mode, detail, prompt_text, detected_lang)
    tokens = _get_tokens(mode, detail)

    body = {
        "model":   model,
        "prompt":  prompt,
        "stream":  True,
        "options": {
            "temperature": 0.25,
            "num_predict": tokens,
            "top_p":       0.9,
            "repeat_penalty": 1.1,
        },
    }
    if images:
        body["images"] = images

    try:
        with requests.post(
            OLLAMA_URL, json=body,
            stream=True,
            timeout=(10, 180),
        ) as resp:
            if resp.status_code != 200:
                yield f"__ERROR__:Ollama error {resp.status_code}: {resp.text[:200]}"
                return

            accumulated = ""
            first_yield = True

            for raw_line in resp.iter_lines():
                if not raw_line:
                    continue
                try:
                    chunk = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue

                token = chunk.get("response", "")
                if token:
                    accumulated += token

                    # On first real content, strip any JSON wrapper the model snuck in
                    if first_yield:
                        cleaned = _strip_json_wrapper(accumulated)
                        if cleaned != accumulated:
                            # Wrapper detected — yield cleaned version and continue
                            accumulated = cleaned
                            if accumulated:
                                yield accumulated
                                first_yield = False
                            continue
                        first_yield = False

                    yield token

                if chunk.get("done"):
                    break

    except requests.Timeout:
        yield "__ERROR__:Ollama timed out. Try a shorter text or lower detail level."
    except requests.ConnectionError:
        yield "__ERROR__:Cannot reach Ollama. Make sure it is running on port 11434."
    except Exception as e:
        yield f"__ERROR__:{str(e)}"


# ════════════════════════════════════════════════════════════════════════════
# NON-STREAMING helpers  (kept for backward compatibility)
# ════════════════════════════════════════════════════════════════════════════
def _call_ollama(model, prompt, images=None, tokens=350, timeout=90):
    body = {
        "model":   model,
        "prompt":  prompt,
        "stream":  False,
        "options": {"temperature": 0.25, "num_predict": tokens, "top_p": 0.9},
    }
    if images:
        body["images"] = images
    r = requests.post(OLLAMA_URL, json=body, timeout=timeout)
    r.raise_for_status()
    return r.json().get("response", "").strip()


def _ok(result, lang):  return {"result": result, "lang": lang, "error": ""}
def _err(msg, lang="english"): return {"result": "", "lang": lang, "error": msg}


def analyze_text(text, mode, detail, lang_override=None):
    lang   = lang_override or detect_language(text)
    prompt = _build_prompt(mode, detail, text, lang)
    try:
        result = _call_ollama(TEXT_MODEL, prompt, tokens=_get_tokens(mode, detail))
        return _ok(result, lang)
    except Exception as e:
        return _err(str(e), lang)


def analyze_image(image_base64, media_type, mode, detail, lang="english"):
    mode_instr   = MODE_PROMPTS.get(mode, MODE_PROMPTS["summary"])
    detail_instr = DETAIL_INSTRUCTIONS.get(detail, DETAIL_INSTRUCTIONS[2])
    prompt = (
        f"Analyze the text and content visible in this image.\n"
        f"{mode_instr} {detail_instr}\n"
        f"Be accurate. If text is unclear say so. No preamble."
    )
    try:
        result = _call_ollama(VISION_MODEL, prompt, images=[image_base64],
                              tokens=_get_tokens(mode, detail), timeout=180)
        return _ok(result, lang)
    except requests.Timeout:
        return _err("Vision model timed out. Try a smaller image.")
    except Exception as e:
        return _err(f"Vision error — is llava:13b pulled? ({e})")


def analyze_file(file_base64, file_name, mode, detail, lang_override=None):
    ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    if ext == "pdf":
        try:
            from pypdf import PdfReader
            pdf_bytes = base64.b64decode(file_base64)
            reader    = PdfReader(io.BytesIO(pdf_bytes))
            text      = "\n\n".join((p.extract_text() or "") for p in reader.pages).strip()
        except ImportError:
            return _err("pypdf not installed. Run: pip install pypdf")
        except Exception as e:
            return _err(f"Could not read PDF: {e}")
        if not text:
            return _err("PDF has no extractable text — upload it as an image instead.")
    else:
        try:
            text = base64.b64decode(file_base64).decode("utf-8", errors="replace").strip()
        except Exception as e:
            return _err(f"Could not decode file: {e}")
    if not text:
        return _err("File appears empty or unreadable.")
    return analyze_text(text[:8000], mode, detail, lang_override)


# ── Internal helper shared by stream_analyze ──────────────────────────────────
def _resolve_content(content_type, text, image_base64, image_media_type,
                     file_base64, file_name, lang_override):
    """Returns (prompt_text, detected_lang, images_list_or_None)."""
    if content_type == "text":
        if not text or not text.strip():
            return "__ERROR__:No text provided.", "english", None
        detected = lang_override or detect_language(text)
        return text.strip(), detected, None

    elif content_type == "image":
        if not image_base64:
            return "__ERROR__:No image data provided.", "english", None
        detected = lang_override or "english"
        prompt   = "Analyze the text and content visible in this image."
        return prompt, detected, [image_base64]

    elif content_type == "file":
        if not file_base64 or not file_name:
            return "__ERROR__:No file data or file_name provided.", "english", None
        ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
        if ext == "pdf":
            try:
                from pypdf import PdfReader
                pdf_bytes = base64.b64decode(file_base64)
                reader    = PdfReader(io.BytesIO(pdf_bytes))
                text_out  = "\n\n".join((p.extract_text() or "") for p in reader.pages).strip()
            except ImportError:
                return "__ERROR__:pypdf not installed. Run: pip install pypdf", "english", None
            except Exception as e:
                return f"__ERROR__:Could not read PDF: {e}", "english", None
            if not text_out:
                return "__ERROR__:PDF has no extractable text.", "english", None
        else:
            try:
                text_out = base64.b64decode(file_base64).decode("utf-8", errors="replace").strip()
            except Exception as e:
                return f"__ERROR__:Could not decode file: {e}", "english", None
        if not text_out:
            return "__ERROR__:File appears empty.", "english", None
        detected = lang_override or detect_language(text_out)
        return text_out[:8000], detected, None

    return "__ERROR__:Unknown content_type.", "english", None