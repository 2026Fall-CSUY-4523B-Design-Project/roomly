"""DTOs for Group Discussion (§8.1.2.7, R-5)."""

import datetime as dt
from typing import Annotated
from uuid import UUID

from pydantic import Field, StringConstraints

from roomly.dto.base import DTO, Distinct
from roomly.dto.common import PersonRef


class PostMessageRequest(DTO):
    """A message in the room, optionally in the thread of one listing or one comparison."""

    body: str = Field(min_length=1, max_length=4000)
    listing_id: UUID | None = None
    comparison_id: UUID | None = None

    def check(self) -> list[tuple[str, str]]:
        if self.listing_id is not None and self.comparison_id is not None:
            return [("comparison_id", "a message belongs to a listing or a comparison, not both")]
        return []


class ReactionRequest(DTO):
    emoji: str = Field(min_length=1, max_length=16)


class CreatePollRequest(DTO):
    question: str = Field(min_length=1, max_length=200)
    options: Annotated[list[Annotated[str, StringConstraints(min_length=1, max_length=120)]], Distinct] = Field(
        min_length=2, max_length=4)


class VoteRequest(DTO):
    option_id: UUID


class ReactionCountDTO(DTO):
    emoji: str
    count: int
    mine: bool


class MessageDTO(DTO):
    id: UUID
    group_id: UUID
    author: PersonRef
    listing_id: UUID | None
    comparison_id: UUID | None
    body: str
    sent_at: dt.datetime
    reactions: list[ReactionCountDTO]


class PollOptionDTO(DTO):
    id: UUID
    position: int
    text: str
    votes: int


class PollDTO(DTO):
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
