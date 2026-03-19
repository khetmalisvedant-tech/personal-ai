import re
import requests
import json
from memory import get_history

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL      = "llama3.2"

MARATHI_KEYWORDS = {
    "आहे","आणि","काय","कसे","मला","तुम्ही","आपण",
    "सांगा","करा","हे","ते","नाही","होय","मराठी",
    "त्याचा","त्याची","आम्ही","तुमचा","कोण","कुठे"
}
HINDI_KEYWORDS = {
    "है","और","क्या","कैसे","मुझे","आप","हम",
    "बताओ","करो","यह","वह","नहीं","हाँ","हिंदी",
    "उसका","उसकी","तुम्हारा","कौन","कहाँ","मैं"
}


def detect_language(text: str) -> str:
    has_devanagari = any("\u0900" <= ch <= "\u097F" for ch in text)
    if not has_devanagari:
        return "english"
    words = set(text.split())
    if words & MARATHI_KEYWORDS:
        return "marathi"
    if words & HINDI_KEYWORDS:
        return "hindi"
    return "hindi"


def _call(prompt: str, max_tokens: int = 300, temperature: float = 0.3) -> str:
    resp = requests.post(
        OLLAMA_URL,
        json={
            "model":   MODEL,
            "prompt":  prompt,
            "stream":  False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                "stop": ["\n\n\n"],
            },
        },
        timeout=90,
    )
    resp.raise_for_status()
    return resp.json().get("response", "").strip()


def _make_summary(explanation: str) -> str:
    sentences = re.split(r'(?<=[.!?])\s+', explanation.strip())
    return sentences[0] if sentences else explanation[:120]


def _make_quiz(user_input: str, explanation: str, lang: str) -> list:
    lang_rule = {
        "marathi": "Reply ONLY in Marathi.",
        "hindi":   "Reply ONLY in Hindi.",
        "english": "Reply ONLY in English.",
    }[lang]

    prompt = (
        f"{lang_rule}\n"
        f"Topic: {user_input}\n"
        f"Context: {explanation[:200]}\n\n"
        f"Write exactly 3 short quiz questions about this topic. "
        f"Number them 1. 2. 3. One per line. Questions only, no answers."
    )
    try:
        raw   = _call(prompt, max_tokens=150, temperature=0.4)
        lines = [l.strip() for l in raw.split("\n") if l.strip()]
        return [re.sub(r"^\d+[\.\)]\s*", "", l) for l in lines][:3]
    except Exception:
        return []


def generate_tutor_response(user_input: str, session_id: str = "default") -> dict:
    lang = detect_language(user_input)

    history      = get_history(session_id)[-4:]
    history_text = "".join(f"{m['role']}: {m['content']}\n" for m in history)

    lang_rule = {
        "marathi": "Reply ONLY in Marathi. Do not use Hindi or English.",
        "hindi":   "Reply ONLY in Hindi. Do not use Marathi or English.",
        "english": "Reply ONLY in English. Do not use Hindi or Marathi.",
    }[lang]

    context_block = f"Previous context:\n{history_text}\n" if history_text.strip() else ""

    # Ask for a plain-text answer — no JSON, no formatting
    explanation_prompt = (
        f"You are a helpful AI tutor. {lang_rule}\n"
        f"{context_block}"
        f"Answer the following question in exactly 2 clear sentences. "
        f"Do NOT repeat or rephrase the question. "
        f"Do NOT use bullet points, JSON, or any formatting. "
        f"Start your answer directly.\n\n"
        f"Question: {user_input}"
    )

    last_error  = None
    explanation = ""

    for attempt in range(2):
        try:
            explanation = _call(explanation_prompt, max_tokens=180, temperature=0.3)
            last_error  = None
            break
        except requests.Timeout:
            last_error = "timeout"
            print(f"⏱ Ollama timeout on attempt {attempt + 1}/2")
        except requests.RequestException as e:
            last_error = str(e)
            print(f"❌ Ollama request error: {e}")
            break

    if last_error:
        msg = (
            "Ollama is taking too long. Please try again."
            if last_error == "timeout"
            else "Could not reach Ollama. Is it running?"
        )
        return {"explanation": msg, "summary": "", "quiz": [], "lang": lang}

    # Guard: strip any accidental JSON wrapper the model produced
    if explanation.lstrip().startswith("{"):
        m = re.search(r'"explanation"\s*:\s*"((?:[^"\\]|\\.)*)"', explanation)
        explanation = m.group(1).replace('\\"', '"').replace('\\n', ' ') if m else explanation

    # Guard: strip echo of the question if model repeated it
    q_norm   = re.sub(r'[^\w\s]', '', user_input).strip().lower()
    ans_norm = re.sub(r'[^\w\s]', '', explanation[:len(user_input) + 15]).strip().lower()
    if ans_norm.startswith(q_norm[:40]):
        explanation = explanation[len(user_input):].lstrip(" :-\n")

    explanation = explanation.strip()

    summary = _make_summary(explanation)
    quiz    = _make_quiz(user_input, explanation, lang)

    print(f"✅ [{lang}] {explanation[:80]}...")

    return {
        "explanation": explanation,
        "summary":     summary,
        "quiz":        quiz,
        "lang":        lang,
    }