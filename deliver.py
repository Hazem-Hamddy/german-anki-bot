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
import asyncio
import logging

import translate
import audio
import packaging

logger = logging.getLogger(__name__)


async def process_sentences_and_get_file(profile: str, deck: str, sentence_items: list) -> str:
    """
    Runs the full pipeline for a batch of German sentences.

    sentence_items: list of dicts, each with:
        "sentence": str (required)
        "translation": str or None (if provided, skips auto-translation)

    Returns the path to the finished .apkg file, ready to send.
    """
    work_dir = tempfile.mkdtemp(prefix="anki_batch_")
    cards = []

    for item in sentence_items:
        sentence = item["sentence"]
        manual_translation = item.get("translation")

        if manual_translation:
            english = manual_translation
            logger.info(f"Using provided translation for: {sentence}")
        else:
            logger.info(f"Translating: {sentence}")
            # translate_sentence is a blocking network call - run it in a
            # background thread so it can't freeze the whole bot if it's slow.
            english = await asyncio.to_thread(translate.translate_sentence, sentence)
            logger.info(f"Translated to: {english}")

        logger.info(f"Generating audio for: {sentence}")
        audio_path = await audio.generate_audio(sentence, output_dir=work_dir)
        logger.info(f"Audio saved to: {audio_path}")

        cards.append({
            "german": sentence,
            "english": english,
            "audio_path": audio_path,
        })

    output_path = os.path.join(work_dir, f"{deck.replace(' ', '_')}.apkg")
    logger.info("Packaging .apkg...")
    # build_package is also blocking (disk I/O) - same reasoning.
    await asyncio.to_thread(packaging.build_package, deck, cards, output_path)
    logger.info("Packaging done.")
    return output_path
