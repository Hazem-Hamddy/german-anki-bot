"""
German Anki Bot - Step 4: Translation

Free, no API key needed. Uses deep-translator's MyMemoryTranslator as the
primary backend, with GoogleTranslator as a fallback.

WHY MyMemory AND NOT GOOGLE AS PRIMARY:
GoogleTranslator (in this library) works by scraping a lightweight Google
Translate page, not by calling a real API. As of late 2026, Google started
blocking that specific scraping method with a CAPTCHA wall, so it now fails
100% of the time - not occasionally, every single call. MyMemory is a real,
legitimate free translation API (not scraping), with a generous anonymous
daily quota, so it's used first. GoogleTranslator is kept as a second
attempt only in case Google's block is ever lifted or is inconsistent.

Requirements (installed on the host, not here):
    pip install deep-translator
"""

import time
from deep_translator import MyMemoryTranslator, GoogleTranslator
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

_executor = ThreadPoolExecutor(max_workers=2)

# A short pause before every translation call, to stay well under
# MyMemory's free anonymous rate/quota limits for a batch of sentences.
DELAY_BETWEEN_CALLS = 0.5  # seconds


def _call_mymemory(german_sentence: str):
    return MyMemoryTranslator(source="de-DE", target="en-GB").translate(german_sentence)


def _call_google(german_sentence: str):
    return GoogleTranslator(source="de", target="en").translate(german_sentence)


def _run_with_timeout(func, german_sentence: str, timeout_seconds: int):
    future = _executor.submit(func, german_sentence)
    return future.result(timeout=timeout_seconds)


def translate_sentence(german_sentence: str, timeout_seconds: int = 10) -> str:
    """Returns the English translation of a German sentence.

    Tries MyMemory first, then falls back to Google's scraping-based
    method if MyMemory fails. If both fail, returns a non-empty fallback
    string rather than "" - this matters: an empty English field makes
    the English->German card's front blank, and Anki silently skips
    generating that card entirely. A guaranteed non-empty value means
    both cards always get created, even if translation truly fails."""
    time.sleep(DELAY_BETWEEN_CALLS)

    for name, func in (("MyMemory", _call_mymemory), ("Google", _call_google)):
        try:
            return _run_with_timeout(func, german_sentence, timeout_seconds)
        except FutureTimeoutError:
            print(f"{name} translation timed out for '{german_sentence}'")
        except Exception as e:
            print(f"{name} translation failed for '{german_sentence}': {e}")

    print(f"All translation backends failed for '{german_sentence}' - using fallback")
    return f"[translation failed: {german_sentence}]"
