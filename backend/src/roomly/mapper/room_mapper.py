"""SQL for group rooms: message, message_reaction, poll, poll_option and poll_vote."""

import datetime as dt
from dataclasses import dataclass
from uuid import UUID

from roomly.entity import Message, Poll, PollOption, Reaction, Vote
from roomly.mapper.base import Mapper, columns

_MESSAGE = columns(Message)
_POLL = columns(Poll)
_OPTION = columns(PollOption)


@dataclass(frozen=True)
class MessageView:
    """A message with its author's display state (a deleted author shows as "Deleted user")."""

    id: UUID
    group_id: UUID
    author_id: UUID | None
    author_name: str | None
    author_deleted: bool
    listing_id: UUID | None
    comparison_id: UUID | None
    body: str
    sent_at: dt.datetime


@dataclass(frozen=True)
class ReactionCount:
    message_id: UUID
    emoji: str
    count: int
    mine: bool


@dataclass(frozen=True)
class OptionTotal:
    option_id: UUID
    votes: int


class MessageMapper(Mapper):
    def insert(
        self, group_id: UUID, author_id: UUID, body: str, listing_id: UUID | None, comparison_id: UUID | None
    ) -> Message:
        sql = f"""
            INSERT INTO message (group_id, author_id, body, listing_id, comparison_id)
            VALUES (%(group_id)s, %(author_id)s, %(body)s, %(listing_id)s, %(comparison_id)s)
            RETURNING {_MESSAGE}"""
        params = {"group_id": group_id, "author_id": author_id, "body": body,
                  "listing_id": listing_id, "comparison_id": comparison_id}
        message = self._one(Message, sql, params)
        assert message is not None
        return message

    def find(self, message_id: UUID) -> Message | None:
        return self._one(Message, f"SELECT {_MESSAGE} FROM message WHERE id = %(id)s", {"id": message_id})

    def list_thread(
        self,
        group_id: UUID,
        *,
        listing_id: UUID | None,
        comparison_id: UUID | None,
        before: dt.datetime | None,
        limit: int,
    ) -> list[MessageView]:
        """Newest first. With neither thread id, the whole room."""
        clauses = ["m.group_id = %(group_id)s"]
        if listing_id is not None:
            clauses.append("m.listing_id = %(listing_id)s")
        if comparison_id is not None:
            clauses.append("m.comparison_id = %(comparison_id)s")
        if before is not None:
            clauses.append("m.sent_at < %(before)s")
        sql = f"""
            SELECT m.id, m.group_id, m.author_id, u.display_name AS author_name,
                   (u.id IS NULL OR u.deleted_at IS NOT NULL) AS author_deleted,
                   m.listing_id, m.comparison_id, m.body, m.sent_at
              FROM message m LEFT JOIN app_user u ON u.id = m.author_id
             WHERE {" AND ".join(clauses)}
             ORDER BY m.sent_at DESC, m.id
             LIMIT %(limit)s"""
        params = {"group_id": group_id, "listing_id": listing_id, "comparison_id": comparison_id,
                  "before": before, "limit": limit}
        return self._all(MessageView, sql, params)


class ReactionMapper(Mapper):
    def upsert(self, message_id: UUID, user_id: UUID, emoji: str) -> Reaction:
        """R-5.2: a second reaction replaces the first."""
        sql = f"""
            INSERT INTO message_reaction (message_id, user_id, emoji) VALUES (%(m)s, %(u)s, %(e)s)
            ON CONFLICT (message_id, user_id) DO UPDATE SET emoji = EXCLUDED.emoji, reacted_at = now()
            RETURNING {columns(Reaction)}"""
        reaction = self._one(Reaction, sql, {"m": message_id, "u": user_id, "e": emoji})
        assert reaction is not None
        return reaction

    def delete(self, message_id: UUID, user_id: UUID) -> int:
        return self._exec("DELETE FROM message_reaction WHERE message_id = %(m)s AND user_id = %(u)s",
                          {"m": message_id, "u": user_id})

    def counts(self, message_ids: list[UUID], viewer_id: UUID) -> list[ReactionCount]:
        sql = f"""
            SELECT message_id, emoji, count(*) AS count, max(CASE WHEN user_id = %(viewer)s THEN 1 ELSE 0 END) = 1 AS mine
              FROM message_reaction WHERE {self.tx.any_of("message_id", "ids", "uuid")}
             GROUP BY message_id, emoji ORDER BY message_id, count(*) DESC, emoji"""
        return self._all(ReactionCount, sql, {"ids": message_ids, "viewer": viewer_id})


class PollMapper(Mapper):
    def insert(self, group_id: UUID, created_by: UUID, question: str) -> Poll:
        sql = f"""
            INSERT INTO poll (group_id, created_by, question) VALUES (%(group_id)s, %(created_by)s, %(question)s)
            RETURNING {_POLL}"""
        poll = self._one(Poll, sql, {"group_id": group_id, "created_by": created_by, "question": question})
        assert poll is not None
        return poll

    def add_option(self, poll_id: UUID, position: int, text: str) -> PollOption:
        sql = f"""
            INSERT INTO poll_option (poll_id, position, text) VALUES (%(poll_id)s, %(position)s, %(text)s)
            RETURNING {_OPTION}"""
        option = self._one(PollOption, sql, {"poll_id": poll_id, "position": position, "text": text})
        assert option is not None
        return option

    def find(self, poll_id: UUID) -> Poll | None:
        return self._one(Poll, f"SELECT {_POLL} FROM poll WHERE id = %(id)s", {"id": poll_id})

    def lock(self, poll_id: UUID) -> Poll | None:
        return self._one(Poll, f"SELECT {_POLL} FROM poll WHERE id = %(id)s FOR UPDATE", {"id": poll_id})

    def list_for_group(self, group_id: UUID) -> list[Poll]:
        return self._all(Poll, f"SELECT {_POLL} FROM poll WHERE group_id = %(id)s ORDER BY created_at DESC", {"id": group_id})

    def options(self, poll_id: UUID) -> list[PollOption]:
        return self._all(PollOption, f"SELECT {_OPTION} FROM poll_option WHERE poll_id = %(id)s ORDER BY position", {"id": poll_id})

    def close(self, poll_id: UUID) -> Poll | None:
        sql = f"UPDATE poll SET state = 'closed', closed_at = now() WHERE id = %(id)s AND state = 'open' RETURNING {_POLL}"
        return self._one(Poll, sql, {"id": poll_id})

    def upsert_vote(self, poll_id: UUID, user_id: UUID, option_id: UUID) -> Vote:
        """R-5.3: one active vote per member, changeable while open (the trigger rejects closed polls)."""
        sql = f"""
            INSERT INTO poll_vote (poll_id, user_id, option_id) VALUES (%(p)s, %(u)s, %(o)s)
            ON CONFLICT (poll_id, user_id) DO UPDATE SET option_id = EXCLUDED.option_id, cast_at = now()
            RETURNING {columns(Vote)}"""
        vote = self._one(Vote, sql, {"p": poll_id, "u": user_id, "o": option_id})
        assert vote is not None
        return vote

    def totals(self, poll_id: UUID) -> list[OptionTotal]:
        """Only votes of current members count (§8.1.2.7 alt. flow 5)."""
        sql = """
            SELECT o.id AS option_id, count(m.id) AS votes
              FROM poll_option o
              JOIN poll p ON p.id = o.poll_id
              LEFT JOIN poll_vote v ON v.option_id = o.id
              LEFT JOIN group_membership m
                     ON m.group_id = p.group_id AND m.user_id = v.user_id AND m.left_at IS NULL
             WHERE o.poll_id = %(id)s
             GROUP BY o.id, o.position ORDER BY o.position"""
        return self._all(OptionTotal, sql, {"id": poll_id})

    def my_vote(self, poll_id: UUID, user_id: UUID) -> UUID | None:
        return self._scalar("SELECT option_id FROM poll_vote WHERE poll_id = %(p)s AND user_id = %(u)s",
                            {"p": poll_id, "u": user_id}, as_type=UUID)
