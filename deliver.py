"""
German Anki Bot - Step 7: Delivering the file back via Telegram

This module ties together everything built so far:
    translate.py  -> English meaning
    audio.py      -> mp3 for each sentence
    packaging.py  -> combines them into a .apkg for the right deck

and sends the finished file back to the user in Telegram.

No new accounts needed for this step - it only uses pieces already built.
"""

import os
import tempfile

import translate
import audio
import packaging


async def process_sentences_and_get_file(profile: str, deck: str, sentences: list) -> str:
    """
    Runs the full pipeline for a batch of German sentences:
    translate each one, generate its audio, package everything into
    a single .apkg for the given deck.

    Returns the path to the finished .apkg file, ready to send.
    """
    work_dir = tempfile.mkdtemp(prefix="anki_batch_")
    cards = []

    for sentence in sentences:
        english = translate.translate_sentence(sentence)
        audio_path = await audio.generate_audio(sentence, output_dir=work_dir)
        cards.append({
            "german": sentence,
            "english": english,
            "audio_path": audio_path,
        })

    output_path = os.path.join(work_dir, f"{deck.replace(' ', '_')}.apkg")
    packaging.build_package(deck, cards, output_path)
    return output_path
