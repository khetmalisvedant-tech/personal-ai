import requests
import os


# Voice map: one voice per language
VOICE_MAP = {
    "english": "en-US-natalie",
    "hindi":   "hi-IN-amit",
    "marathi": "hi-IN-amit",   # Murf uses Hindi voice for Marathi (same script)
}


def generate_voice(text: str, lang: str = "english"):
    MURF_API_KEY = os.getenv("MURF_API_KEY")

    if not MURF_API_KEY:
        print("❌ MURF API KEY NOT FOUND")
        return None

    voice_id = VOICE_MAP.get(lang, "en-US-natalie")

    url = "https://api.murf.ai/v1/speech/generate"

    payload = {
        "text": text.strip()[:500],
        "voiceId": voice_id,
        "format": "mp3"
    }

    headers = {
        "api-key": MURF_API_KEY,
        "Content-Type": "application/json"
    }

    try:
        print(f"🔊 Sending to Murf [{lang} → {voice_id}]:", text[:80])

        response = requests.post(url, json=payload, headers=headers)

        print("🔁 Status Code:", response.status_code)

        if response.status_code != 200:
            print("❌ Murf Error:", response.text)
            return None

        data = response.json()
        audio_url = data.get("audioFile")

        if not audio_url:
            print("❌ No audioFile in response:", data)
            return None

        print("✅ Audio Generated:", audio_url)
        return audio_url

    except Exception as e:
        print("❌ Murf Exception:", e)
        return None
