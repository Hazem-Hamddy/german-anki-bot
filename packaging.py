"""
German Anki Bot - Step 6: Packaging into .apkg (genanki)

Requirements (installed on the host, not here):
    pip install genanki

HOW DECK MATCHING WORKS (read this once):
Anki matches decks by their exact NAME when importing an .apkg - not by
some hidden ID you configure. So to add a brand new deck in the future,
you do NOT need to touch this file. Just type the new deck's exact name
when the bot asks "Which deck?" (the "+ New deck" option from Step 2).
This file turns that name into a stable ID automatically (via a hash),
so the same deck name always produces the same package target.

One rule to remember: the name you type in the bot must match your
Anki deck's name EXACTLY (case + spelling), or Anki will create a new,
separate deck instead of adding to your existing one.
"""

import hashlib
import genanki

# Fixed note type (model) shared by every deck - one card layout for all
# your German decks. Its ID must stay constant forever once cards exist,
# so it's hardcoded here rather than derived.
MODEL_ID = 1607392319  # arbitrary fixed number, do not change later
NOTE_MODEL = genanki.Model(
    MODEL_ID,
    "German Sentence Model",
    fields=[
        {"name": "German"},
        {"name": "English"},
        {"name": "Audio"},
    ],
    templates=[
        {
            "name": "Card 1",
            "qfmt": '<div class="german">{{German}}</div><div class="audio">{{Audio}}</div>',
            "afmt": '{{FrontSide}}<hr id="answer"><div class="english">{{English}}</div>',
        },
    ],
    css="""
.card {
    text-align: center;
    font-family: arial;
}
.german {
    font-size: 32px;
    font-weight: bold;
}
.english {
    font-size: 26px;
}
.audio {
    margin-top: 10px;
}
""",
)


def _deck_id_for(deck_name: str) -> int:
    """Turns a deck name into a stable numeric ID.
    Same name -> same ID, every time, forever (including across bot
    restarts) - this is what lets you add new decks just by typing a
    new name, with no manual ID setup needed, ever."""
    digest = hashlib.sha256(deck_name.encode("utf-8")).hexdigest()
    return int(digest, 16) % (10 ** 10)


def build_package(deck_name: str, cards: list, output_path: str) -> str:
    """
    cards: list of dicts, each with keys:
        "german": str
        "english": str
        "audio_path": str (path to the mp3 from audio.py)

    Returns the path to the created .apkg file.
    """
    deck = genanki.Deck(_deck_id_for(deck_name), deck_name)
    media_files = []

    for card in cards:
        audio_filename = card["audio_path"].split("/")[-1]
        note = genanki.Note(
            model=NOTE_MODEL,
            fields=[
                card["german"],
                card["english"],
                f"[sound:{audio_filename}]",
            ],
        )
        deck.add_note(note)
        media_files.append(card["audio_path"])

    package = genanki.Package(deck)
    package.media_files = media_files
    package.write_to_file(output_path)
    return output_path
