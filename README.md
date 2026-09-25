# German Anki Bot — Telegram bot that turns sentences into ready-made Anki flashcards

A Telegram bot that lets you send German sentences (typed, or as a `.txt`/`.csv` file)
from your phone, and automatically get back a ready-to-import Anki deck: each sentence
gets translated to English, given natural-sounding AI-generated audio, and packaged
into a `.apkg` file with **two-directional flashcards** (German→English *and*
English→German). It supports multiple people (profiles) and multiple decks per
person, so it works for a household or a small group of friends, not just one user.

This document explains everything that was built, why, and how to set it up from
scratch — enough for someone else to clone this repo and run their own copy.

---

## 1. What problem this solves

Manually making Anki cards with audio is slow: you have to find or record audio for
each sentence, cut it if it's from a video, convert formats, and add it to the right
card in the right deck. This bot automates all of that:

```
You (phone, Telegram) → type/send a sentence
                       → bot translates it (free)
                       → bot generates natural audio for it (free)
                       → bot packages it into a real Anki file
                       → bot sends the file back to you
You → tap the file → cards land in your existing Anki deck, progress untouched
```

---

## 2. Architecture overview

- **Telegram** is just the chat interface — a free bot account, no server of its own.
- **The bot's Python code** runs on a **cloud host** (see §7), listening for your
  messages 24/7. It never needs your PC or phone to be on.
- **Airtable** stores your profiles, decks, and a history log of every sentence sent
  — free, no server maintenance, viewable as a normal spreadsheet-like table.
- **Translation and audio generation** are done with free libraries, no external
  accounts needed for those two specifically.
- **genanki** (a Python library) builds the actual `.apkg` file — no Anki program
  needs to be open anywhere for this to work.

Nothing in this project needs a paid API key. The only recurring cost, if any, is
hosting (see §7 for the honest tradeoffs there).

---

## 3. Accounts you need to set this up yourself

| Account | Why | Cost |
|---|---|---|
| Telegram | Lets you create a bot | Free |
| Airtable | Stores profiles/decks/history | Free |
| A hosting service (Railway, Render, Fly.io, etc.) | Runs the bot 24/7 | Free tier or a few $/month — see §7 |
| GitHub | Holds the code so the host can deploy it | Free |

No Google Cloud, no paid translation API, no paid TTS API.

---

## 4. File-by-file explanation

All files live in one flat folder (no subfolders) so the hosting platform can find
and run them directly.

### `bot.py` — the conversation flow (the "brain")
Handles every Telegram interaction: button taps, typed messages, file uploads. Built
with `python-telegram-bot`'s `ConversationHandler`, which models the chat as a state
machine:

```
/start (or any message)
  → CHOOSING_PROFILE   ("Whose profile is this for?")
  → CHOOSING_DECK      ("Which deck?" — offers to reuse your last one)
  → CHOOSING_FORMAT     ("Type text / .txt file / .csv file")
  → RECEIVING_CONTENT   (waits for your sentence(s) or file)
  → CONFIRMING_CONTENT  (shows what it parsed, asks you to confirm before processing)
  → processing → sends back the .apkg file
```

Every screen has a **⬅️ Back** and **❌ Cancel** button, so a wrong tap never traps
you — you can back up one step or bail out entirely at any point.

### `storage.py` — persistent storage (Airtable)
All profile/deck/history data lives in an Airtable base with two tables:

**`Profiles` table** (fields): `telegram_user_id`, `profile_name`, `last_deck`,
`hidden_decks`

**`Log` table** (fields): `timestamp`, `telegram_user_id`, `profile`, `deck`,
`sentence`, `status`

Every function in this file is keyed by `telegram_user_id`, so different people using
the same bot never see each other's profiles or decks — this is what makes it safe
to share with a friend.

**Why Airtable and not Google Sheets:** the original plan used Google Sheets, but
many Google accounts (including personal ones) are now covered by an org policy
(`iam.disableServiceAccountKeyCreation`) that blocks downloading the credential file
needed to connect to Sheets from code. Airtable's free personal access token has no
such restriction, so it was used instead. No other part of the design changed.

### `translate.py` — translation
Uses `deep-translator`'s `GoogleTranslator` wrapper — free, no API key. Runs with a
10-second timeout so a slow/stuck network call can't silently freeze the whole bot
(see §8, this was a real bug that was fixed this way).

### `audio.py` — audio generation
Uses `edge-tts`, a library that calls Microsoft Edge's built-in neural
text-to-speech voices for free. Key settings:
- `GERMAN_VOICE` — currently `de-DE-SeraphinaMultilingualNeural` (a newer, more
  natural-sounding voice than the default `KatjaNeural`).
- `SPEECH_RATE = "-15%"` — slows speech down, since the default pace was reported as
  too fast/robotic-sounding.
- 15-second timeout, same reasoning as translation.

**Honest caveat:** `edge-tts` is an *unofficial* wrapper around a Microsoft service
not meant for third-party use. It can occasionally break with a `403` error when
Microsoft changes an internal auth token — this happened during development and was
fixed by updating to the latest `edge-tts` version. It may recur; if it does, check
for a newer `edge-tts` release first.

### `packaging.py` — builds the actual Anki file
Uses `genanki` to build a `.apkg` file, with:
- A **fixed deck ID derived from the deck's exact name** (via a stable SHA-256 hash)
  — meaning Anki matches by name on import, so cards land in your existing deck
  rather than creating a duplicate. To add a new deck in the future, you never touch
  this file — you just type a new deck name in the bot, and it's handled
  automatically.
- A **note model with two templates** — one for German→English, one for
  English→German — so every sentence produces **two cards**, letting you practice
  recall in both directions (same idea as Anki's built-in "Basic (and reversed
  card)" type).
- CSS styling for large, readable text that adapts to Anki's light/dark mode
  (an earlier version hardcoded a gray color for the English side, which was nearly
  invisible in dark mode — fixed by removing the manual color and letting it inherit
  the theme's default).

**Important Anki behavior to know:** Anki does **not** update an existing note
type's templates on import if a note type with the same internal ID already exists
in your collection — it keeps whatever's already stored locally. This bit us during
development: adding the second (reversed) card template had no effect until the
model's ID was deliberately changed, forcing Anki to treat it as a new note type.
**Do not change `MODEL_ID` in `packaging.py` again** once you have real cards, or
you'll hit this exact issue.

### `deliver.py` — ties everything together
Runs the full pipeline for a batch of sentences: translate → generate audio →
package into a `.apkg`. Supports:
- An optional **manual translation override** per sentence (used by `.csv` uploads
  that supply their own translation column).
- An optional **progress callback**, called after each sentence finishes, so the bot
  can show "Processing 3 of 10..." instead of going silent on longer batches.

All the slow/blocking parts of this pipeline are run via `asyncio.to_thread` so a
slow network call can't freeze the bot for other users (see §8).

### `fileparse.py` — parses uploaded `.txt`/`.csv` files
- `.txt`: one sentence per line, every line auto-translated.
- `.csv`: needs a header row with a `sentence` column, and optionally a
  `translation` column. Rows with a filled-in translation skip auto-translation;
  empty ones still get auto-translated.

### `manage.py` — `/manage` command
Lets you delete profiles and decks without editing Airtable by hand:
- Lists your profiles, each with a 🗑 delete button.
- Tap a profile to see its decks, each with its own 🗑 delete button.
- **Deleting a deck only hides it from future pickers** — the sentence history for
  it stays in the Log table untouched. Deleting a profile removes just that
  profile's row; its history stays too. Nothing is ever destructively deleted from
  your history log by this command.

### `requirements.txt` — dependencies
```
python-telegram-bot==21.6
pyairtable==2.3.3
deep-translator==1.11.4
edge-tts==7.2.8
genanki==0.13.1
```

### `Procfile` — tells the host how to start the bot
```
worker: python bot.py
```

---

## 5. Environment variables (secrets — never hardcode these in the code)

| Variable | Where it comes from |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Message **@BotFather** on Telegram → `/newbot` → follow the prompts |
| `AIRTABLE_TOKEN` | airtable.com → Developer hub → Create token (scopes: `data.records:read`, `data.records:write`, `schema.bases:read`; access: your base) |
| `AIRTABLE_BASE_ID` | Open your Airtable base → Help → API documentation → shown at the top, looks like `appXXXXXXXXXXXXXX` |

These are set in your hosting platform's dashboard (e.g. Railway's "Variables" tab),
never committed to the code — `storage.py` and `bot.py` read them via
`os.environ.get(...)`.

---

## 6. Airtable setup (one-time, ~10 minutes)

1. Create a free Airtable account.
2. Create a new Base named exactly `AnkiBotData`.
3. Create a table named `Profiles` with fields (all "Single line text"):
   `telegram_user_id`, `profile_name`, `last_deck`, `hidden_decks`
4. Create a table named `Log` with fields (all "Single line text"):
   `timestamp`, `telegram_user_id`, `profile`, `deck`, `sentence`, `status`
5. Get your Base ID (see table above).
6. Create a personal access token (see table above).

**Field type note:** if you see an error like `Cannot parse value "X" for field Y`,
it means Airtable auto-created that column as something other than "Single line
text" (e.g. "Single select"). `storage.py` already passes `typecast=True` on every
write to work around this automatically, but changing the column type to "Single
line text" directly in Airtable is the cleaner long-term fix.

---

## 7. Hosting — the honest tradeoffs

This project was originally built assuming Railway's free tier was permanent. It
changed in 2026 to a one-time $5 trial credit plus only ~$1/month free after that —
not enough to keep a bot running continuously without eventually stalling.

Options, with real tradeoffs:

| Host | Free tier for this use case? | Notes |
|---|---|---|
| **Railway** | Effectively no (as of 2026) | ~$1/mo free after a one-time $5 credit; cheap paid tier ($5/mo Hobby) if you don't mind a small cost |
| **Render** | No free tier for **Background Workers** (the correct service type for a bot) | Only their free **Web Service** tier is free, and that spins down after 15 minutes of inactivity — would need a keep-alive workaround (a tiny HTTP server + an external pinger like UptimeRobot) to stay always-on |
| **Fly.io** | Yes, free allowance fits a small always-on bot | Different deploy process (CLI-based rather than a web dashboard) |

**Deployment steps (works the same for Railway or Render, just swap the platform
name):**
1. Push all the files in this repo to a GitHub repository.
2. Create a new project on your chosen host, connect it to this GitHub repo.
3. For Railway: it auto-detects `Procfile` and `requirements.txt`.
   For Render: create a **Background Worker** (not Web Service), with build command
   `pip install -r requirements.txt` and start command `python bot.py`.
4. Add the 3 environment variables from §5.
5. Deploy, then check the logs for `Bot starting (polling mode)...` with no errors.
6. Message your bot on Telegram — if it replies asking "Whose profile is this for?",
   it's live.

**If you ever run two instances of the bot at once** (e.g. mid-migration between
hosts), you'll see a `409 Conflict` error in the logs — Telegram only allows one
active connection per bot token. Stop/delete the old deployment once the new one is
confirmed working.

---

## 8. Bugs encountered during development, and their real fixes

Documented here because these are non-obvious and easy to reintroduce if the code is
modified later.

**Bot froze completely after one message, including for other users.**
Root cause: several functions (`storage.log_sentence`, `translate.translate_sentence`,
`packaging.build_package`) made blocking, synchronous network/disk calls directly
inside the bot's async code. Python's single-threaded event loop means one stuck
call froze *everything*, not just that one conversation. Fixed by wrapping every
blocking call in `asyncio.to_thread(...)`, and adding explicit timeouts (10s for
translation, 15s for audio) so a stuck call fails loudly instead of hanging forever.

**Airtable writes failing with `422 Client Error: Unprocessable Entity`.**
Root cause: a column (e.g. `profile`) had been auto-created by Airtable as a type
other than "Single line text" (e.g. "Single select"), which rejects values it
doesn't already recognize as an option. Fixed by adding `typecast=True` to every
Airtable write call, which tells Airtable to accept and convert the value instead
of rejecting it.

**AnkiDroid import error: `Failed to read '...apkg': stream did not contain valid
UTF-8`.**
This is a known, currently-open bug in AnkiDroid itself (unrelated to this bot),
related to how it opens files directly from another app's cache via Android's
scoped storage. Workaround: save the file to your phone's storage first (don't tap
"Open in Anki" directly from Telegram), then use AnkiDroid's own "Import File" menu
to browse to it.

**Cards only showed one direction (German→English), even after adding a second,
reversed card template.**
Root cause: Anki does not update an existing note type's templates on import if a
note type with the same ID already exists locally — it silently keeps whatever's
already there. Fixed by changing `MODEL_ID` in `packaging.py` to a new number, which
forces Anki to treat it as a genuinely new note type. Previously imported cards stay
single-sided permanently (no retroactive fix, short of deleting and re-adding them);
only new imports get the fix.

**`edge-tts` audio generation failing with `403 Invalid response status` on the
`speech.platform.bing.com` websocket.**
`edge-tts` is an unofficial wrapper, and Microsoft periodically changes an internal
auth mechanism it depends on. Fixed by updating to the latest `edge-tts` release.
This can recur in the future; if it does, check for a newer version first.

**Uploaded `.csv`/`.txt` files sometimes needing to be sent twice.**
Root cause: the file-download step (`doc.get_file()` /
`download_as_bytearray()`) had no exception handling, so a transient network hiccup
during download silently killed the conversation with no error message — resending
happened to succeed on the second try. Fixed by wrapping the download step in a
try/except that reports a clear error and lets you retry without restarting the
whole profile/deck/format flow.

---

## 9. Features currently working

- Multi-profile, multi-deck support, fully isolated per Telegram user.
- Remembers your last-used deck per profile, so you don't retype it every time.
- Accepts sentences as typed text, `.txt` upload, or `.csv` upload (with optional
  manual translations per row).
- Confirmation screen before processing — shows what was parsed, lets you confirm,
  re-send, or cancel, so a typo doesn't waste a translation+audio call.
- Progress indicator ("Processing 3 of 10...") for batches larger than one sentence.
- Every card is two-directional (German→English and English→German).
- Large, theme-adaptive (light/dark mode safe) card text.
- `⬅️ Back` and `❌ Cancel` buttons on every step of the conversation.
- `/manage` command to delete profiles and hide/delete decks without touching
  Airtable directly.
- Full sentence history logged in Airtable (`Log` table), independent of what's
  currently shown in the bot's pickers.

---

## 10. Known limitations / ideas not yet built

- **One tap still required to import** the `.apkg` into Anki — there's no way to
  push cards directly into AnkiDroid without a phone-side companion app (AnkiDroid
  does expose a Content Provider API for this, but it requires a separate Android
  app, not just a cloud bot).
- **Duplicate detection** — sending the same sentence twice currently just creates
  a second identical card; no check against history yet.
- **`/stats` command** — a summary like "214 cards total, 12 this week" isn't built
  yet, though the data for it already exists in the Log table.
- **Retry button on pipeline failure** — currently you'd have to retype/resend a
  failed batch from scratch.
- **Voice message input** — sending a voice note instead of typing isn't supported;
  would need a free speech-to-text step added to the pipeline.
