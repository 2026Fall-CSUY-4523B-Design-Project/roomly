"""DTOs for Group Discussion (§8.1.2.7, R-5)."""

import datetime as dt
from dataclasses import dataclass
from uuid import UUID

from roomly.dto.base import rule
from roomly.dto.common import PersonRef


@dataclass(frozen=True)
class PostMessageRequest:
    """A message in the room, optionally in the thread of one listing or one comparison."""

    body: str = rule(min_len=1, max_len=4000)
    listing_id: UUID | None = None
    comparison_id: UUID | None = None

    def check(self) -> list[tuple[str, str]]:
        if self.listing_id is not None and self.comparison_id is not None:
            return [("comparison_id", "a message belongs to a listing or a comparison, not both")]
        return []


@dataclass(frozen=True)
class MessageCursor:
    """``?before=<ISO time>``: page back through a room."""

    before: dt.datetime


@dataclass(frozen=True)
class ReactionRequest:
    emoji: str = rule(min_len=1, max_len=16)


@dataclass(frozen=True)
class CreatePollRequest:
    question: str = rule(min_len=1, max_len=200)
    options: list[str] = rule(min_items=2, max_items=4, unique=True)

    def check(self) -> list[tuple[str, str]]:
        if any(not o.strip() or len(o.strip()) > 120 for o in self.options):
            return [("options", "each option must be 1-120 characters")]
        return []


@dataclass(frozen=True)
class VoteRequest:
    option_id: UUID


@dataclass(frozen=True)
class ReactionCountDTO:
    emoji: str
    count: int
    mine: bool


@dataclass(frozen=True)
class MessageDTO:
    id: UUID
    group_id: UUID
    author: PersonRef
    listing_id: UUID | None
    comparison_id: UUID | None
    body: str
    sent_at: dt.datetime
    reactions: list[ReactionCountDTO]


@dataclass(frozen=True)
class PollOptionDTO:
    id: UUID
    position: int
    text: str
    votes: int


@dataclass(frozen=True)
class PollDTO:
    """Totals count current members only. A poll result is not a rental commitment."""

    id: UUID
    group_id: UUID
    question: str
    state: str
    created_by: UUID | None
    created_at: dt.datetime
    closed_at: dt.datetime | None
    options: list[PollOptionDTO]
    total_votes: int
    my_vote: UUID | None
