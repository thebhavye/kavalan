"""Language detection/handling hooks for Hindi, Tamil and English.

Scaffold: script-range heuristics only. A real STT/TTS + LLM integration
replaces the internals; the function signatures stay.
"""
from __future__ import annotations


def _in_range(text: str, lo: int, hi: int) -> bool:
    return any(lo <= ord(ch) <= hi for ch in text)


def detect_language(text: str) -> str:
    """Return 'hi' (Hindi/Devanagari), 'ta' (Tamil) or 'en' (default)."""
    if _in_range(text, 0x0B80, 0x0BFF):
        return "ta"
    if _in_range(text, 0x0900, 0x097F):
        return "hi"
    lowered = text.lower()
    if any(w in lowered for w in ["bijli", "bill bhar", "beta ko", "bhej do", "kya"]):
        return "hi"
    return "en"


REPLIES = {
    "allowed": {
        "en": "Done. {detail}",
        "hi": "Ho gaya. {detail}",
        "ta": "Mudinthathu. {detail}",
    },
    "held": {
        "en": "This needs family approval first. Please approve here: {url}",
        "hi": "Iske liye parivaar ki anumati chahiye. Yahan approve karein: {url}",
        "ta": "Itharku kudumba anumathi venum. Inge approve seyyungal: {url}",
    },
    "blocked": {
        "en": "I can't do that — it is blocked by our safety policy. {reason}",
        "hi": "Main yeh nahin kar sakta — suraksha niyam ke tahat mana hai. {reason}",
        "ta": "Ennal ithai seiya mudiyathu — paathukaappu vithi thadukkirathu. {reason}",
    },
}


def reply(kind: str, lang: str, **kwargs: str) -> str:
    template = REPLIES.get(kind, REPLIES["blocked"]).get(lang, REPLIES[kind]["en"])
    return template.format(**kwargs)
