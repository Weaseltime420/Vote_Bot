from __future__ import annotations

import asyncio
import os
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

import db as vote_db


def _env_int(name: str) -> Optional[int]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return None
    return int(raw)


def _db_path() -> str:
    return os.getenv("DB_PATH", "votes.db").strip() or "votes.db"


def _format_standings(rows: list[vote_db.VoteStandingRow], total: int) -> str:
    if not rows:
        return "No vote options have been set yet. Use `/setvote` first."
    lines = [f"{r.option_id}. {r.label} — {r.votes}" for r in rows]
    lines.append("")
    lines.append(f"Total votes: {total}")
    return "\n".join(lines)


intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready() -> None:
    # Initialize DB on startup (idempotent).
    await vote_db.init_db(_db_path())

    guild_id = _env_int("GUILD_ID")
    if guild_id is not None:
        guild = discord.Object(id=guild_id)
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
        print(f"Synced commands to guild {guild_id}. Logged in as {bot.user}.")
    else:
        await bot.tree.sync()
        print(f"Synced global commands. Logged in as {bot.user}.")


@bot.tree.command(name="setvote", description="Set vote options (admin only). Resets existing votes.")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(
    option1="First option (required)",
    option2="Second option (required)",
    option3="Third option (optional)",
    option4="Fourth option (optional)",
    option5="Fifth option (optional)",
    option6="Sixth option (optional)",
    option7="Seventh option (optional)",
    option8="Eighth option (optional)",
    option9="Ninth option (optional)",
    option10="Tenth option (optional)",
)
async def setvote(
    interaction: discord.Interaction,
    option1: str,
    option2: str,
    option3: Optional[str] = None,
    option4: Optional[str] = None,
    option5: Optional[str] = None,
    option6: Optional[str] = None,
    option7: Optional[str] = None,
    option8: Optional[str] = None,
    option9: Optional[str] = None,
    option10: Optional[str] = None,
) -> None:
    labels = [option1, option2]
    for opt in (option3, option4, option5, option6, option7, option8, option9, option10):
        if opt is not None:
            labels.append(opt)

    try:
        count = await vote_db.set_vote_options(_db_path(), labels)
    except ValueError as e:
        await interaction.response.send_message(str(e), ephemeral=True)
        return

    options = await vote_db.list_vote_options(_db_path())
    rendered = "\n".join([f"{i}. {label}" for i, label in options])
    await interaction.response.send_message(
        f"Vote options set ({count}). Existing votes were cleared.\n\n{rendered}",
        ephemeral=True,
    )


@bot.tree.command(name="vote", description="Cast your vote (one-time).")
@app_commands.describe(choice="The number corresponding to the option set by /setvote")
async def vote(interaction: discord.Interaction, choice: int) -> None:
    await vote_db.init_db(_db_path())

    user_id = interaction.user.id
    if await vote_db.user_has_voted(_db_path(), user_id):
        await interaction.response.send_message("User has already voted")
        return

    if not await vote_db.option_exists(_db_path(), choice):
        opts = await vote_db.list_vote_options(_db_path())
        if not opts:
            await interaction.response.send_message(
                "No vote options have been set yet. An admin must run `/setvote` first.",
                ephemeral=True,
            )
            return
        rendered = "\n".join([f"{i}. {label}" for i, label in opts])
        await interaction.response.send_message(
            f"Invalid choice. Please vote using one of these numbers:\n\n{rendered}",
            ephemeral=True,
        )
        return

    try:
        await vote_db.cast_vote(_db_path(), user_id, choice)
    except Exception:
        # Covers rare race conditions (double-submit) or db errors.
        if await vote_db.user_has_voted(_db_path(), user_id):
            await interaction.response.send_message("User has already voted")
        else:
            await interaction.response.send_message(
                "Sorry, something went wrong recording your vote.",
                ephemeral=True,
            )
        return

    await interaction.response.send_message("Thank you for voting")


@bot.tree.command(name="clearvotes", description="Clear all current votes (admin only).")
@app_commands.checks.has_permissions(administrator=True)
async def clearvotes(interaction: discord.Interaction) -> None:
    await vote_db.init_db(_db_path())
    await vote_db.clear_votes(_db_path())
    await interaction.response.send_message("Votes cleared. (Vote options were kept.)", ephemeral=True)


@bot.tree.command(name="checkvote", description="Check current standings (admin only, ephemeral).")
@app_commands.checks.has_permissions(administrator=True)
async def checkvote(interaction: discord.Interaction) -> None:
    await vote_db.init_db(_db_path())
    rows = await vote_db.get_vote_standings(_db_path())
    total = await vote_db.get_total_votes(_db_path())
    msg = _format_standings(rows, total)
    await interaction.response.send_message(msg, ephemeral=True)


@bot.tree.command(name="publishvote", description="Publish final vote results (admin only).")
@app_commands.checks.has_permissions(administrator=True)
async def publishvote(interaction: discord.Interaction) -> None:
    await vote_db.init_db(_db_path())
    rows = await vote_db.get_vote_standings(_db_path())
    total = await vote_db.get_total_votes(_db_path())
    msg = _format_standings(rows, total)
    await interaction.response.send_message(msg, ephemeral=False)


@bot.tree.command(name="showpoll", description="Show the available vote options.")
async def showpoll(interaction: discord.Interaction) -> None:
    await vote_db.init_db(_db_path())
    options = await vote_db.list_vote_options(_db_path())
    if not options:
        await interaction.response.send_message(
            "No vote options have been set yet. An admin must run `/setvote` first."
        )
        return

    rendered = "\n".join([f"{i}. {label}" for i, label in options])
    await interaction.response.send_message(f"Vote options:\n\n{rendered}", ephemeral=False)


@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
) -> None:
    if isinstance(error, app_commands.MissingPermissions):
        if interaction.response.is_done():
            await interaction.followup.send("Administrator permission required.", ephemeral=True)
        else:
            await interaction.response.send_message(
                "Administrator permission required.", ephemeral=True
            )
        return

    # Fallback: don't leak details to public channels.
    if interaction.response.is_done():
        await interaction.followup.send("Command failed.", ephemeral=True)
    else:
        await interaction.response.send_message("Command failed.", ephemeral=True)

    raise error


async def main() -> None:
    load_dotenv()
    token = os.getenv("DISCORD_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "Missing DISCORD_TOKEN. Create a .env file (see example.env) and set DISCORD_TOKEN."
        )

    await vote_db.init_db(_db_path())

    async with bot:
        await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())


