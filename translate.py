"""
German Anki Bot - Step 4: Translation

Free, no API key needed. Uses deep-translator's GoogleTranslator wrapper.

Requirements (installed on the host, not here):
    pip install deep-translator
"""

import time
from deep_translator import GoogleTranslator
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

_translator = GoogleTranslator(source="de", target="en")
_executor = ThreadPoolExecutor(max_workers=2)

# A short pause before every translation call. Without this, sending many
# sentences back-to-back (e.g. a 27-word list) can trip the free Google
# Translate endpoint's rate limiting, causing failures.
DELAY_BETWEEN_CALLS = 0.5  # seconds


def _translate_once(german_sentence: str, timeout_seconds: int):
    future = _executor.submit(_translator.translate, german_sentence)
    return future.result(timeout=timeout_seconds)


def translate_sentence(german_sentence: str, timeout_seconds: int = 10) -> str:
    """Returns the English translation of a German sentence.

    Retries once on failure/timeout before giving up. If both attempts
    fail, returns a non-empty fallback string rather than "" - this
    matters: an empty English field makes the English->German card's
    front blank, and Anki silently skips generating that card entirely.
    A guaranteed non-empty value means both cards always get created,
    even on the rare case both translation attempts fail."""
    time.sleep(DELAY_BETWEEN_CALLS)

    for attempt in (1, 2):
        try:
            return _translate_once(german_sentence, timeout_seconds)
        except FutureTimeoutError:
            print(f"Translation timed out for '{german_sentence}' (attempt {attempt})")
        except Exception as e:
            print(f"Translation failed for '{german_sentence}' (attempt {attempt}): {e}")
        if attempt == 1:
            time.sleep(1.5)  # brief backoff before retrying

    print(f"Both translation attempts failed for '{german_sentence}' - using fallback")
    return f"[translation failed: {german_sentence}]"
