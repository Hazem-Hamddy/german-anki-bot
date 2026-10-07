"""
German Anki Bot - Step 4: Translation

Free, no API key needed. Tries GoogleTranslator first, falls back to
MyMemoryTranslator if Google fails.

CONTEXT ON THIS ORDER:
GoogleTranslator (in this library) works by scraping a lightweight Google
Translate page, not by calling a real API. As of late 2026, Google started
blocking that specific scraping method with a CAPTCHA wall, so it currently
fails on most/all calls. MyMemoryTranslator is a real, legitimate free
translation API (not scraping) and was previously made the primary backend
for reliability. This version flips the order back to Google-first,
MyMemory-fallback, on the chance Google's block is inconsistent or lifted -
at the cost of an extra failed call (and a little latency) on every
sentence while Google's block is still in effect.

Requirements (installed on the host, not here):
    pip install deep-translator
"""

import time
from deep_translator import GoogleTranslator, MyMemoryTranslator
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

_executor = ThreadPoolExecutor(max_workers=2)

# A short pause before every translation call, to stay well under
# MyMemory's free anonymous rate/quota limits for a batch of sentences.
DELAY_BETWEEN_CALLS = 0.5  # seconds


def _call_google(german_sentence: str):
    return GoogleTranslator(source="de", target="en").translate(german_sentence)


def _call_mymemory(german_sentence: str):
    return MyMemoryTranslator(source="de-DE", target="en-GB").translate(german_sentence)


def _run_with_timeout(func, german_sentence: str, timeout_seconds: int):
    future = _executor.submit(func, german_sentence)
    return future.result(timeout=timeout_seconds)


def translate_sentence(german_sentence: str, timeout_seconds: int = 10) -> str:
    """Returns the English translation of a German sentence.

    Tries Google first, then falls back to MyMemory if Google fails.
    If both fail, returns a non-empty fallback string rather than "" -
    this matters: an empty English field makes the English->German
    card's front blank, and Anki silently skips generating that card
    entirely. A guaranteed non-empty value means both cards always get
    created, even if translation truly fails."""
    time.sleep(DELAY_BETWEEN_CALLS)

    for name, func in (("Google", _call_google), ("MyMemory", _call_mymemory)):
        try:
            return _run_with_timeout(func, german_sentence, timeout_seconds)
        except FutureTimeoutError:
            print(f"{name} translation timed out for '{german_sentence}'")
        except Exception as e:
            print(f"{name} translation failed for '{german_sentence}': {e}")

    print(f"All translation backends failed for '{german_sentence}' - using fallback")
    return f"[translation failed: {german_sentence}]"
