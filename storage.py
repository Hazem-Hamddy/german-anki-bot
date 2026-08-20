"""
German Anki Bot - Step 3: Persistent storage (Airtable)

Same function names/signatures as the Google Sheets version, so bot.py
does NOT need to change - only this file was rewritten.

Airtable base "AnkiBotData" expected with two tables:

Table "Profiles" (fields):
    telegram_user_id | profile_name | last_deck

Table "Log" (fields):
    timestamp | telegram_user_id | profile | deck | sentence | status

Requirements (installed on the host, not here):
    pip install pyairtable
"""

import os
import datetime
import logging
from pyairtable import Api
import requests

logger = logging.getLogger(__name__)

# --- Config: set these as environment variables on Railway (Step 8) ---
# Never hardcode real credentials here - this file goes into GitHub.
AIRTABLE_TOKEN = os.environ.get("AIRTABLE_TOKEN")
AIRTABLE_BASE_ID = os.environ.get("AIRTABLE_BASE_ID")

_api = Api(AIRTABLE_TOKEN, timeout=(5, 10))  # (connect timeout, read timeout) in seconds
_profiles_table = _api.table(AIRTABLE_BASE_ID, "Profiles")
_log_table = _api.table(AIRTABLE_BASE_ID, "Log")


# --- Profiles ---

def get_profiles(telegram_user_id: str):
    """Returns list of profile names this Telegram user has created."""
    records = _profiles_table.all(formula=f"{{telegram_user_id}} = '{telegram_user_id}'")
    return [r["fields"].get("profile_name") for r in records]


def create_profile(telegram_user_id: str, profile_name: str):
    _profiles_table.create({
        "telegram_user_id": str(telegram_user_id),
        "profile_name": profile_name,
        "last_deck": "",
    }, typecast=True)


def get_decks(telegram_user_id: str, profile_name: str):
    """Distinct deck names this profile has used, derived from the Log table."""
    formula = (
        f"AND({{telegram_user_id}} = '{telegram_user_id}', "
        f"{{profile}} = '{profile_name}')"
    )
    records = _log_table.all(formula=formula)
    decks = []
    for r in records:
        deck = r["fields"].get("deck")
        if deck and deck not in decks:
            decks.append(deck)
    return decks


def _find_profile_record(telegram_user_id: str, profile_name: str):
    formula = (
        f"AND({{telegram_user_id}} = '{telegram_user_id}', "
        f"{{profile_name}} = '{profile_name}')"
    )
    records = _profiles_table.all(formula=formula)
    return records[0] if records else None


def get_last_deck(telegram_user_id: str, profile_name: str):
    record = _find_profile_record(telegram_user_id, profile_name)
    if record:
        return record["fields"].get("last_deck") or None
    return None


def save_deck_choice(telegram_user_id: str, profile_name: str, deck_name: str):
    record = _find_profile_record(telegram_user_id, profile_name)
    if record:
        _profiles_table.update(record["id"], {"last_deck": deck_name}, typecast=True)
    else:
        # profile row not found for this user - create it
        _profiles_table.create({
            "telegram_user_id": str(telegram_user_id),
            "profile_name": profile_name,
            "last_deck": deck_name,
        }, typecast=True)


# --- Sentence log (also functions as your history / debug trail) ---

def log_sentence(telegram_user_id: str, profile: str, deck: str, sentence: str, status: str = "queued"):
    try:
        _log_table.create({
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "telegram_user_id": str(telegram_user_id),
            "profile": profile,
            "deck": deck,
            "sentence": sentence,
            "status": status,
        }, typecast=True)
        # typecast=True tells Airtable to accept any text value even if a
        # column was accidentally created as "Single select" instead of
        # "Single line text" - this is what was causing the 422 error.
    except requests.exceptions.HTTPError as e:
        # Surface Airtable's actual error message (e.g. "unknown field name")
        # instead of a generic traceback that hides the real cause.
        body = e.response.text if e.response is not None else "(no response body)"
        logger.error(f"Airtable rejected log_sentence: {body}")
        raise


def mark_status(telegram_user_id: str, sentence: str, new_status: str):
    """Finds the most recent matching row for this sentence and updates its status."""
    formula = (
        f"AND({{telegram_user_id}} = '{telegram_user_id}', "
        f"{{sentence}} = '{sentence}')"
    )
    records = _log_table.all(formula=formula)
    if records:
        # Airtable doesn't guarantee order; sort by timestamp to get the most recent
        records.sort(key=lambda r: r["fields"].get("timestamp", ""))
        latest = records[-1]
        _log_table.update(latest["id"], {"status": new_status}, typecast=True)


def get_queued_sentences(telegram_user_id: str = None):
    """
    Returns all Log rows with status == 'queued'.
    Used by the Step 4-6 processing pipeline to know what's left to do.
    If telegram_user_id is given, filters to just that user.
    """
    if telegram_user_id:
        formula = (
            f"AND({{telegram_user_id}} = '{telegram_user_id}', "
            f"{{status}} = 'queued')"
        )
    else:
        formula = "{status} = 'queued'"
    records = _log_table.all(formula=formula)
    return [r["fields"] for r in records]
