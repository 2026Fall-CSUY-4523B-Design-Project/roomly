"""RoomService (§9.1 control class): messages, reactions and polls in a group room (R-5).

Every action re-checks current membership on the server, so a member who left or was
removed can no longer read, post, react or vote. Realtime push over WebSocket (the 1 s
delivery target) is Sprint 5; clients poll ``GET /groups/{id}/messages`` until then.
"""

import datetime as dt
from uuid import UUID

from roomly.db import Database
from roomly.dto.room import (
    CreatePollRequest,
    MessageDTO,
    PollDTO,
    PostMessageRequest,
    ReactionCountDTO,
    ReactionRequest,
    VoteRequest,
)
from roomly.entity import User


class RoomService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def list_messages(
        self,
        user: User,
        group_id: UUID,
        *,
        listing_id: UUID | None,
        comparison_id: UUID | None,
        before: dt.datetime | None,
        limit: int,
    ) -> list[MessageDTO]:
        raise NotImplementedError

    def post_message(self, user: User, group_id: UUID, req: PostMessageRequest) -> MessageDTO:
        raise NotImplementedError

    def react(self, user: User, message_id: UUID, req: ReactionRequest) -> list[ReactionCountDTO]:
        raise NotImplementedError

    def unreact(self, user: User, message_id: UUID) -> list[ReactionCountDTO]:
        raise NotImplementedError

    def create_poll(self, user: User, group_id: UUID, req: CreatePollRequest) -> PollDTO:
        raise NotImplementedError

    def list_polls(self, user: User, group_id: UUID) -> list[PollDTO]:
        raise NotImplementedError

    def get_poll(self, user: User, poll_id: UUID) -> PollDTO:
        raise NotImplementedError

    def vote(self, user: User, poll_id: UUID, req: VoteRequest) -> PollDTO:
        raise NotImplementedError

    def close_poll(self, user: User, poll_id: UUID) -> PollDTO:
        """R-5.4: the creator or the group owner closes voting."""
        raise NotImplementedError
