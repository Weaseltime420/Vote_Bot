# VOTE_BOT (Discord Blind Voting Bot)

Simple “rough and ready” Discord bot for **blind voting** using **slash commands**, **Python 3.13**, and **SQLite**.

## What it does

- **/setvote (admin)**: sets vote options (minimum 2; up to 10) and **clears existing votes**
- **/vote (public)**: accepts an integer choice; stores `(discord_user_id, choice)`; prevents double-voting
- **/clearvotes (admin)**: clears all votes (keeps the current vote options)
- **/checkvote (admin)**: shows current vote standings (**ephemeral**)
- **/publishvote (admin)**: posts final vote results (**not ephemeral**)

## Setup

1) Install Python 3.13, then in this folder:

```bash
py -3.13 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

2) Create a `.env` file (copy `example.env` to `.env`) and fill in:

- `DISCORD_TOKEN`
- (optional) `GUILD_ID` (recommended while developing; syncs commands faster)
- (optional) `DB_PATH` (defaults to `votes.db`)

3) Run the bot:

```bash
py -3.13 bot.py
```

## Discord configuration notes

- When inviting the bot, include scopes: `bot` and `applications.commands`.
- The admin-only commands use Discord’s **Administrator** permission check.


