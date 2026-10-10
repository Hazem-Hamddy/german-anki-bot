"""
German Anki Bot - Step 5: Audio generation

Free, no API key needed. Uses Microsoft's edge-tts neural voices.

Requirements (installed on the host, not here):
    pip install edge-tts
"""

import hashlib
import asyncio
import edge_tts

# German-only voices (these only know German pronunciation, so they can't
# mistake a short word like "null" for English the way a multilingual
# voice can). To switch, change GERMAN_VOICE to one of these:
#   "de-DE-AmalaNeural"                  <- female, German-only (current)
#   "de-DE-ConradNeural"                 <- male, German-only
#   "de-DE-KillianNeural"                <- male, German-only
#   "de-DE-KatjaNeural"                  <- female, German-only, but can sound clipped/fast
#   "de-DE-SeraphinaMultilingualNeural"  <- multilingual: natural-sounding, but guesses the
#                                           language from context, so isolated words
#                                           (e.g. "null") can come out sounding English
# Voice names can change on Microsoft's side. If one stops working, run
# `edge-tts --list-voices` on the host to see what's currently available.
GERMAN_VOICE = "de-DE-AmalaNeural"

# Negative = slower. "-15%" noticeably slows speech without distorting pitch.
SPEECH_RATE = "-15%"


def _filename_for(sentence: str) -> str:
    """Turns a sentence into a short, safe, unique filename so re-runs
    don't collide and we don't have to worry about special characters."""
    h = hashlib.sha1(sentence.encode("utf-8")).hexdigest()[:12]
    return f"audio_{h}.mp3"


async def generate_audio(sentence: str, output_dir: str = ".", timeout_seconds: int = 15) -> str:
    """Generates an mp3 for the given German sentence.
    Returns the file path it was saved to.
    Raises TimeoutError if edge-tts doesn't respond in time, instead of
    hanging forever (this is the fix for the silent-freeze bug)."""
    filename = _filename_for(sentence)
    path = f"{output_dir}/{filename}"
    communicate = edge_tts.Communicate(sentence, GERMAN_VOICE, rate=SPEECH_RATE)
    await asyncio.wait_for(communicate.save(path), timeout=timeout_seconds)
    return path
