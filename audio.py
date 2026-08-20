"""
German Anki Bot - Step 5: Audio generation

Free, no API key needed. Uses Microsoft's edge-tts neural voices.

Requirements (installed on the host, not here):
    pip install edge-tts
"""

import hashlib
import edge_tts

# A natural-sounding female German voice. Full voice list:
# run `edge-tts --list-voices` on the host if you want to pick a different one.
GERMAN_VOICE = "de-DE-KatjaNeural"


def _filename_for(sentence: str) -> str:
    """Turns a sentence into a short, safe, unique filename so re-runs
    don't collide and we don't have to worry about special characters."""
    h = hashlib.sha1(sentence.encode("utf-8")).hexdigest()[:12]
    return f"audio_{h}.mp3"


async def generate_audio(sentence: str, output_dir: str = ".") -> str:
    """Generates an mp3 for the given German sentence.
    Returns the file path it was saved to."""
    filename = _filename_for(sentence)
    path = f"{output_dir}/{filename}"
    communicate = edge_tts.Communicate(sentence, GERMAN_VOICE)
    await communicate.save(path)
    return path
