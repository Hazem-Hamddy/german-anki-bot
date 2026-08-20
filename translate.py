"""
German Anki Bot - Step 4: Translation

Free, no API key needed. Uses deep-translator's GoogleTranslator wrapper.

Requirements (installed on the host, not here):
    pip install deep-translator
"""

from deep_translator import GoogleTranslator
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

_translator = GoogleTranslator(source="de", target="en")
_executor = ThreadPoolExecutor(max_workers=2)


def translate_sentence(german_sentence: str, timeout_seconds: int = 10) -> str:
    """Returns the English translation of a German sentence.
    If translation fails OR takes longer than timeout_seconds, returns an
    empty string rather than hanging the pipeline (a card can still be
    made, just without an English meaning, and you can fill it in later)."""
    future = _executor.submit(_translator.translate, german_sentence)
    try:
        return future.result(timeout=timeout_seconds)
    except FutureTimeoutError:
        print(f"Translation timed out for '{german_sentence}'")
        return ""
    except Exception as e:
        print(f"Translation failed for '{german_sentence}': {e}")
        return ""
