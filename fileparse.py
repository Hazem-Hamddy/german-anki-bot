"""
German Anki Bot - file parsing for .txt / .csv uploads

Turns raw file bytes into the list-of-dicts format deliver.py expects:
    [{"sentence": "...", "translation": "..." or None}, ...]

No new accounts/libraries needed - uses Python's built-in csv module.
"""

import csv
import io


def parse_txt(file_bytes: bytes) -> list:
    """One sentence per line. No translations (always auto-translated)."""
    text = file_bytes.decode("utf-8")
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    return [{"sentence": line, "translation": None} for line in lines]


def parse_csv(file_bytes: bytes) -> list:
    """
    Expects a header row with a 'sentence' column and an optional
    'translation' column. Example:

        sentence,translation
        Ich muss gehen,I have to go
        Guten Morgen,

    Rows with an empty/missing translation get auto-translated,
    same as .txt uploads.
    """
    text = file_bytes.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))

    if reader.fieldnames is None or "sentence" not in [f.strip().lower() for f in reader.fieldnames]:
        raise ValueError(
            "CSV must have a 'sentence' column in the header row "
            "(and optionally a 'translation' column)."
        )

    # Normalize header casing so "Sentence" / "SENTENCE" etc. all work
    field_map = {f.strip().lower(): f for f in reader.fieldnames}
    sentence_key = field_map["sentence"]
    translation_key = field_map.get("translation")

    items = []
    for row in reader:
        sentence = (row.get(sentence_key) or "").strip()
        if not sentence:
            continue
        translation = None
        if translation_key:
            raw = (row.get(translation_key) or "").strip()
            translation = raw if raw else None
        items.append({"sentence": sentence, "translation": translation})
    return items
