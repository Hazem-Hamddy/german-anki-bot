"""
German Anki Bot - Step 4: Translation

Free, no API key needed. Uses deep-translator's GoogleTranslator wrapper.

Requirements (installed on the host, not here):
    pip install deep-translator
"""

from deep_translator import GoogleTranslator

_translator = GoogleTranslator(source="de", target="en")


def translate_sentence(german_sentence: str) -> str:
    """Returns the English translation of a German sentence.
    If translation fails for any reason, returns an empty string
    rather than crashing the pipeline (a card can still be made,
    just without an English meaning, and you can fill it in later)."""
    try:
        return _translator.translate(german_sentence)
    except Exception as e:
        print(f"Translation failed for '{german_sentence}': {e}")
        return ""
