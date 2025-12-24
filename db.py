from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

import aiosqlite


@dataclass(frozen=True)
class VoteStandingRow:
    option_id: int
    label: str
    votes: int


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS vote_options (
  option_id INTEGER PRIMARY KEY,
  label TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS votes (
  user_id INTEGER PRIMARY KEY,
  option_id INTEGER NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY(option_id) REFERENCES vote_options(option_id)
);
"""


async def init_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.executescript(SCHEMA_SQL)
        await db.commit()


async def set_vote_options(db_path: str, labels: Iterable[str]) -> int:
    labels_list = [l.strip() for l in labels if l and l.strip()]
    if len(labels_list) < 2:
        raise ValueError("At least 2 non-empty vote options are required.")

    async with aiosqlite.connect(db_path) as db:
        await db.execute("PRAGMA foreign_keys = ON;")
        async with db.execute("BEGIN;"):
            # Reset options and votes to avoid mismatched/invalid votes.
            await db.execute("DELETE FROM votes;")
            await db.execute("DELETE FROM vote_options;")

            for idx, label in enumerate(labels_list, start=1):
                await db.execute(
                    "INSERT INTO vote_options(option_id, label) VALUES(?, ?);",
                    (idx, label),
                )

        await db.commit()
    return len(labels_list)


async def list_vote_options(db_path: str) -> list[tuple[int, str]]:
    async with aiosqlite.connect(db_path) as db:
        cur = await db.execute(
            "SELECT option_id, label FROM vote_options ORDER BY option_id ASC;"
        )
        rows = await cur.fetchall()
        return [(int(r[0]), str(r[1])) for r in rows]


async def user_has_voted(db_path: str, user_id: int) -> bool:
    async with aiosqlite.connect(db_path) as db:
        cur = await db.execute("SELECT 1 FROM votes WHERE user_id = ?;", (user_id,))
        row = await cur.fetchone()
        return row is not None


async def option_exists(db_path: str, option_id: int) -> bool:
    async with aiosqlite.connect(db_path) as db:
        cur = await db.execute(
            "SELECT 1 FROM vote_options WHERE option_id = ?;", (option_id,)
        )
        row = await cur.fetchone()
        return row is not None


async def cast_vote(db_path: str, user_id: int, option_id: int) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute("PRAGMA foreign_keys = ON;")
        await db.execute(
            "INSERT INTO votes(user_id, option_id) VALUES(?, ?);",
            (user_id, option_id),
        )
        await db.commit()


async def clear_votes(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute("DROP TABLE IF EXISTS votes;")
        await db.execute(
            """
            CREATE TABLE votes (
              user_id INTEGER PRIMARY KEY,
              option_id INTEGER NOT NULL,
              created_at TEXT NOT NULL DEFAULT (datetime('now')),
              FOREIGN KEY(option_id) REFERENCES vote_options(option_id)
            );
            """
        )
        await db.commit()


async def get_vote_standings(db_path: str) -> list[VoteStandingRow]:
    async with aiosqlite.connect(db_path) as db:
        await db.execute("PRAGMA foreign_keys = ON;")
        cur = await db.execute(
            """
            SELECT
              o.option_id,
              o.label,
              COALESCE(COUNT(v.user_id), 0) AS votes
            FROM vote_options o
            LEFT JOIN votes v ON v.option_id = o.option_id
            GROUP BY o.option_id, o.label
            ORDER BY o.option_id ASC;
            """
        )
        rows = await cur.fetchall()
        return [VoteStandingRow(int(r[0]), str(r[1]), int(r[2])) for r in rows]


async def get_total_votes(db_path: str) -> int:
    async with aiosqlite.connect(db_path) as db:
        cur = await db.execute("SELECT COUNT(*) FROM votes;")
        row = await cur.fetchone()
        return int(row[0]) if row else 0


async def get_vote_label(db_path: str, option_id: int) -> Optional[str]:
    async with aiosqlite.connect(db_path) as db:
        cur = await db.execute(
            "SELECT label FROM vote_options WHERE option_id = ?;", (option_id,)
        )
        row = await cur.fetchone()
        return str(row[0]) if row else None


