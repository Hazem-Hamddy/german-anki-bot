"""
German Anki Bot - Manage: delete/edit saved profiles & decks

Adds a /manage command, separate from the main add-a-sentence flow.

Deleting a deck doesn't erase its sentence history in the Log table -
it just hides it from future "which deck?" pickers (see storage.hide_deck).
Deleting a profile removes the profile row itself; its Log history stays.
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
)
import storage

MANAGE_MENU, MANAGE_PROFILE = range(100, 102)  # high numbers so they never clash with bot.py's states


async def manage_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    context.user_data["manage_user_id"] = user_id
    profiles = storage.get_profiles(user_id)

    if not profiles:
        await update.message.reply_text("No saved profiles yet.")
        return ConversationHandler.END

    buttons = [
        [InlineKeyboardButton(p, callback_data=f"mgmt_open:{p}"),
         InlineKeyboardButton("🗑 Delete", callback_data=f"mgmt_delprofile:{p}")]
        for p in profiles
    ]
    buttons.append([InlineKeyboardButton("✅ Done", callback_data="mgmt_done")])
    await update.message.reply_text(
        "Manage profiles — tap a name to manage its decks, or 🗑 to delete the profile:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return MANAGE_MENU


async def open_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    profile = query.data.split(":", 1)[1]
    context.user_data["manage_profile"] = profile
    return await show_decks(update, context)


async def show_decks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = context.user_data["manage_user_id"]
    profile = context.user_data["manage_profile"]
    decks = storage.get_decks(user_id, profile)

    buttons = [
        [InlineKeyboardButton(d, callback_data="noop"),
         InlineKeyboardButton("🗑 Delete", callback_data=f"mgmt_deldeck:{d}")]
        for d in decks
    ]
    buttons.append([InlineKeyboardButton("⬅️ Back to profiles", callback_data="mgmt_back")])
    text = f"Decks for {profile}:" if decks else f"No decks yet for {profile}."
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    return MANAGE_PROFILE


async def delete_deck(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer("Deck hidden.")
    deck = query.data.split(":", 1)[1]
    user_id = context.user_data["manage_user_id"]
    profile = context.user_data["manage_profile"]
    storage.hide_deck(user_id, profile, deck)
    return await show_decks(update, context)


async def delete_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer("Profile deleted.")
    profile = query.data.split(":", 1)[1]
    user_id = context.user_data["manage_user_id"]
    storage.delete_profile(user_id, profile)
    # Re-show the profile list
    profiles = storage.get_profiles(user_id)
    if not profiles:
        await query.edit_message_text("No saved profiles left.")
        return ConversationHandler.END
    buttons = [
        [InlineKeyboardButton(p, callback_data=f"mgmt_open:{p}"),
         InlineKeyboardButton("🗑 Delete", callback_data=f"mgmt_delprofile:{p}")]
        for p in profiles
    ]
    buttons.append([InlineKeyboardButton("✅ Done", callback_data="mgmt_done")])
    await query.edit_message_text(
        "Manage profiles — tap a name to manage its decks, or 🗑 to delete the profile:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return MANAGE_MENU


async def back_to_profiles(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_id = context.user_data["manage_user_id"]
    profiles = storage.get_profiles(user_id)
    buttons = [
        [InlineKeyboardButton(p, callback_data=f"mgmt_open:{p}"),
         InlineKeyboardButton("🗑 Delete", callback_data=f"mgmt_delprofile:{p}")]
        for p in profiles
    ]
    buttons.append([InlineKeyboardButton("✅ Done", callback_data="mgmt_done")])
    await query.edit_message_text(
        "Manage profiles — tap a name to manage its decks, or 🗑 to delete the profile:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return MANAGE_MENU


async def done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Done managing.")
    return ConversationHandler.END


async def noop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    return MANAGE_PROFILE


def build_manage_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("manage", manage_start)],
        states={
            MANAGE_MENU: [
                CallbackQueryHandler(open_profile, pattern=r"^mgmt_open:"),
                CallbackQueryHandler(delete_profile, pattern=r"^mgmt_delprofile:"),
                CallbackQueryHandler(done, pattern=r"^mgmt_done$"),
            ],
            MANAGE_PROFILE: [
                CallbackQueryHandler(delete_deck, pattern=r"^mgmt_deldeck:"),
                CallbackQueryHandler(back_to_profiles, pattern=r"^mgmt_back$"),
                CallbackQueryHandler(noop, pattern=r"^noop$"),
            ],
        },
        fallbacks=[],
    )
