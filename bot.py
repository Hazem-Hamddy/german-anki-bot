"""
German Anki Bot - Step 2: Conversation flow
(profile -> deck -> format -> content)

This file ONLY handles the conversation/menu logic.
Storage (Step 3), translation (Step 4), TTS (Step 5), and
packaging (Step 6) are stubbed here as placeholder functions
that we'll fill in in later steps.

Requirements (installed on the host in Step 8, not here):
    pip install python-telegram-bot==21.*
"""

import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
import storage  # Step 3: real Google Sheets storage
import deliver  # Step 7: translate + audio + packaging pipeline

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ---- Token comes from an environment variable, not hardcoded in this file ----
# On Railway (Step 8), you'll set TELEGRAM_BOT_TOKEN in the dashboard.
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

# Conversation states
CHOOSING_PROFILE, CHOOSING_DECK, NEW_DECK_NAME, CHOOSING_FORMAT, RECEIVING_CONTENT = range(5)

# Storage is now real (Airtable via storage.py) instead of an in-memory dict.
# Every call below needs the Telegram user's id, so profiles/decks are kept
# separate per person automatically (this is what makes it safe to share
# with a friend - your data and theirs never mix).


# --- Conversation steps ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point: /start or any message when idle. Ask which profile."""
    user_id = update.effective_user.id
    context.user_data["telegram_user_id"] = user_id
    profiles = storage.get_profiles(user_id)
    buttons = [[InlineKeyboardButton(p, callback_data=f"profile:{p}")] for p in profiles]
    buttons.append([InlineKeyboardButton("+ New profile", callback_data="profile:__new__")])
    await update.message.reply_text(
        "Whose profile is this for?",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return CHOOSING_PROFILE


async def profile_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    profile = query.data.split(":", 1)[1]

    if profile == "__new__":
        await query.edit_message_text("Type the new profile's name:")
        context.user_data["awaiting_new_profile"] = True
        return CHOOSING_PROFILE

    context.user_data["profile"] = profile
    user_id = context.user_data["telegram_user_id"]
    last_deck = storage.get_last_deck(user_id, profile)

    if last_deck:
        buttons = [
            [InlineKeyboardButton(f"Yes, use '{last_deck}'", callback_data=f"deck:{last_deck}")],
            [InlineKeyboardButton("Choose a different deck", callback_data="deck:__choose__")],
        ]
        await query.edit_message_text(
            f"Last time you used '{last_deck}' for {profile}. Use it again?",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
    else:
        return await ask_deck(update, context, edit=True)

    return CHOOSING_DECK


async def new_profile_named(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the text reply when user typed a brand-new profile name."""
    name = update.message.text.strip()
    user_id = context.user_data["telegram_user_id"]
    storage.create_profile(user_id, name)
    context.user_data["profile"] = name
    context.user_data["awaiting_new_profile"] = False
    return await ask_deck(update, context, edit=False)


async def ask_deck(update: Update, context: ContextTypes.DEFAULT_TYPE, edit: bool) -> int:
    profile = context.user_data["profile"]
    user_id = context.user_data["telegram_user_id"]
    decks = storage.get_decks(user_id, profile)
    buttons = [[InlineKeyboardButton(d, callback_data=f"deck:{d}")] for d in decks]
    buttons.append([InlineKeyboardButton("+ New deck", callback_data="deck:__new__")])
    text = f"Which deck for {profile}?"
    markup = InlineKeyboardMarkup(buttons)
    if edit:
        await update.callback_query.edit_message_text(text, reply_markup=markup)
    else:
        await update.message.reply_text(text, reply_markup=markup)
    return CHOOSING_DECK


async def deck_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    deck = query.data.split(":", 1)[1]

    if deck == "__choose__":
        return await ask_deck(update, context, edit=True)

    if deck == "__new__":
        await query.edit_message_text("Type the new deck's exact name (must match Anki):")
        return NEW_DECK_NAME

    context.user_data["deck"] = deck
    user_id = context.user_data["telegram_user_id"]
    storage.save_deck_choice(user_id, context.user_data["profile"], deck)
    return await ask_format(update, context, edit=True)


async def new_deck_named(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    deck = update.message.text.strip()
    context.user_data["deck"] = deck
    user_id = context.user_data["telegram_user_id"]
    storage.save_deck_choice(user_id, context.user_data["profile"], deck)
    return await ask_format(update, context, edit=False)


async def ask_format(update: Update, context: ContextTypes.DEFAULT_TYPE, edit: bool) -> int:
    buttons = [
        [InlineKeyboardButton("Type text", callback_data="format:text")],
        [InlineKeyboardButton(".txt file", callback_data="format:txt")],
        [InlineKeyboardButton(".csv file", callback_data="format:csv")],
    ]
    text = "How do you want to send the sentences?"
    markup = InlineKeyboardMarkup(buttons)
    if edit:
        await update.callback_query.edit_message_text(text, reply_markup=markup)
    else:
        await update.message.reply_text(text, reply_markup=markup)
    return CHOOSING_FORMAT


async def format_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    fmt = query.data.split(":", 1)[1]
    context.user_data["format"] = fmt

    prompts = {
        "text": "Send your sentence(s) now, one per line if more than one.",
        "txt": "Send your .txt file now.",
        "csv": "Send your .csv file now (columns: sentence, translation [optional]).",
    }
    await query.edit_message_text(prompts[fmt])
    return RECEIVING_CONTENT


async def content_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Logs each sentence, then runs the full pipeline (translate + audio +
    package) and sends the finished .apkg back in this chat."""
    profile = context.user_data["profile"]
    deck = context.user_data["deck"]
    fmt = context.user_data["format"]
    user_id = context.user_data["telegram_user_id"]

    if fmt == "text":
        sentences = [s.strip() for s in update.message.text.split("\n") if s.strip()]
    else:
        # .txt / .csv file handling is not wired up yet - only plain text
        # messages run the full pipeline for now.
        await update.message.reply_text(
            "File uploads aren't wired up to the pipeline yet — for now, "
            "please type or paste your sentence(s) as a text message."
        )
        return ConversationHandler.END

    for s in sentences:
        storage.log_sentence(user_id, profile, deck, s, status="queued")

    await update.message.reply_text(f"Got it — processing {len(sentences)} sentence(s)...")

    apkg_path = await deliver.process_sentences_and_get_file(profile, deck, sentences)

    with open(apkg_path, "rb") as f:
        await update.message.reply_document(
            document=f,
            filename=f"{deck}.apkg",
            caption=f"{len(sentences)} card(s) for {profile} → '{deck}'. Tap to import into Anki.",
        )

    for s in sentences:
        storage.mark_status(user_id, s, "done")

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Cancelled. Send anything to start over.")
    return ConversationHandler.END


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(filters.TEXT & ~filters.COMMAND, start),
        ],
        states={
            CHOOSING_PROFILE: [
                CallbackQueryHandler(profile_chosen, pattern=r"^profile:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, new_profile_named),
            ],
            CHOOSING_DECK: [CallbackQueryHandler(deck_chosen, pattern=r"^deck:")],
            NEW_DECK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, new_deck_named)],
            CHOOSING_FORMAT: [CallbackQueryHandler(format_chosen, pattern=r"^format:")],
            RECEIVING_CONTENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, content_received),
                MessageHandler(filters.Document.ALL, content_received),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv)
    logger.info("Bot starting (polling mode)...")
    app.run_polling()


if __name__ == "__main__":
    main()
