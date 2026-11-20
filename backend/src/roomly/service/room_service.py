"""RoomService (§9.1 control class): messages, reactions and polls in a group room (R-5).

Every action re-checks current membership on the server, so a member who left or was
removed can no longer read, post, react or vote. Realtime push over WebSocket (the 1 s
delivery target) is Sprint 5; clients poll ``GET /groups/{id}/messages`` until then.
"""

import datetime as dt
from collections import defaultdict
from uuid import UUID

from roomly.db import Database, Tx
from roomly.dto.common import PersonRef
from roomly.dto.room import (
    CreatePollRequest,
    MessageDTO,
    PollDTO,
    PollOptionDTO,
    PostMessageRequest,
    ReactionCountDTO,
    ReactionRequest,
    VoteRequest,
)
from roomly.entity import Message, Poll, User
from roomly.mapper.comparison_mapper import ComparisonMapper
from roomly.mapper.listing_mapper import ListingMapper
from roomly.mapper.room_mapper import (
    MessageMapper,
    MessageView,
    PollMapper,
    ReactionMapper,
)
from roomly.service.access import require_member
from roomly.service.errors import Conflict, Forbidden, NotFound
from roomly.service.notification_events import notify_message


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
        with self.db.transaction() as tx:
            require_member(tx, group_id, user)
            views = MessageMapper(tx).list_thread(
                group_id, listing_id=listing_id, comparison_id=comparison_id, before=before, limit=limit)
            return self._messages(tx, views, user)

    def post_message(self, user: User, group_id: UUID, req: PostMessageRequest) -> MessageDTO:
        with self.db.transaction() as tx:
            group, _ = require_member(tx, group_id, user)
            if req.listing_id is not None and ListingMapper(tx).find(req.listing_id) is None:
                raise NotFound("Listing not found.")
            if req.comparison_id is not None:
                comparison = ComparisonMapper(tx).find(req.comparison_id)
                if comparison is None or comparison.group_id != group_id:
                    raise NotFound("Comparison not found in this group.")
            message = MessageMapper(tx).insert(group_id, user.id, req.body, req.listing_id, req.comparison_id)
            notify_message(tx, group, message, _name(user))
            view = MessageView(
                id=message.id, group_id=message.group_id, author_id=message.author_id,
                author_name=user.display_name, author_deleted=False, listing_id=message.listing_id,
                comparison_id=message.comparison_id, body=message.body, sent_at=message.sent_at,
            )
            return self._messages(tx, [view], user)[0]

    def react(self, user: User, message_id: UUID, req: ReactionRequest) -> list[ReactionCountDTO]:
        with self.db.transaction() as tx:
            message = self._message(tx, message_id)
            require_member(tx, message.group_id, user)
            ReactionMapper(tx).upsert(message.id, user.id, req.emoji)
            return self._reactions(tx, message.id, user)

    def unreact(self, user: User, message_id: UUID) -> list[ReactionCountDTO]:
        with self.db.transaction() as tx:
            message = self._message(tx, message_id)
            require_member(tx, message.group_id, user)
            ReactionMapper(tx).delete(message.id, user.id)
            return self._reactions(tx, message.id, user)

    def create_poll(self, user: User, group_id: UUID, req: CreatePollRequest) -> PollDTO:
        with self.db.transaction() as tx:
            require_member(tx, group_id, user)
            polls = PollMapper(tx)
            poll = polls.insert(group_id, user.id, req.question)
            for position, text in enumerate(req.options, start=1):
                polls.add_option(poll.id, position, text)
            return self._poll(tx, poll, user)

    def list_polls(self, user: User, group_id: UUID) -> list[PollDTO]:
        with self.db.transaction() as tx:
            require_member(tx, group_id, user)
            return [self._poll(tx, poll, user) for poll in PollMapper(tx).list_for_group(group_id)]

    def get_poll(self, user: User, poll_id: UUID) -> PollDTO:
        with self.db.transaction() as tx:
            poll = self._poll_of_member(tx, poll_id, user)
            return self._poll(tx, poll, user)

    def vote(self, user: User, poll_id: UUID, req: VoteRequest) -> PollDTO:
        with self.db.transaction() as tx:
            polls = PollMapper(tx)
            poll = polls.lock(poll_id)
            if poll is None:
                raise NotFound("Poll not found.")
            require_member(tx, poll.group_id, user)
            if poll.state == "closed":
                raise Conflict("This poll is closed.")
            if req.option_id not in {option.id for option in polls.options(poll.id)}:
                raise NotFound("That option is not part of this poll.")
            polls.upsert_vote(poll.id, user.id, req.option_id)
            return self._poll(tx, poll, user)

    def close_poll(self, user: User, poll_id: UUID) -> PollDTO:
        """R-5.4: the creator or the group owner closes voting."""
        with self.db.transaction() as tx:
            polls = PollMapper(tx)
            poll = polls.lock(poll_id)
            if poll is None:
                raise NotFound("Poll not found.")
            _, membership = require_member(tx, poll.group_id, user)
            if poll.state == "closed":
                raise Conflict("This poll is already closed.")
            if poll.created_by != user.id and not membership.is_owner:
                raise Forbidden("Only the creator or the group owner can close this poll.")
            closed = polls.close(poll.id)
            assert closed is not None
            return self._poll(tx, closed, user)

    @staticmethod
    def _message(tx: Tx, message_id: UUID) -> Message:
        message = MessageMapper(tx).find(message_id)
        if message is None:
            raise NotFound("Message not found.")
        return message

    @staticmethod
    def _poll_of_member(tx: Tx, poll_id: UUID, user: User) -> Poll:
        poll = PollMapper(tx).find(poll_id)
        if poll is None:
            raise NotFound("Poll not found.")
        require_member(tx, poll.group_id, user)
        return poll

    @staticmethod
    def _messages(tx: Tx, views: list[MessageView], user: User) -> list[MessageDTO]:
        counts = ReactionMapper(tx).counts([view.id for view in views], user.id) if views else []
        by_message: dict[UUID, list[ReactionCountDTO]] = defaultdict(list)
        for count in counts:
            by_message[count.message_id].append(
                ReactionCountDTO(emoji=count.emoji, count=count.count, mine=count.mine))
        return [
            MessageDTO(
                id=view.id, group_id=view.group_id,
                author=PersonRef.of(view.author_id, view.author_name, view.author_deleted),
                listing_id=view.listing_id, comparison_id=view.comparison_id, body=view.body,
                sent_at=view.sent_at, reactions=by_message.get(view.id, []),
            )
            for view in views
        ]

    @staticmethod
    def _reactions(tx: Tx, message_id: UUID, user: User) -> list[ReactionCountDTO]:
        return [ReactionCountDTO(emoji=c.emoji, count=c.count, mine=c.mine)
                for c in ReactionMapper(tx).counts([message_id], user.id)]

    @staticmethod
    def _poll(tx: Tx, poll: Poll, user: User) -> PollDTO:
        polls = PollMapper(tx)
        options = polls.options(poll.id)
        totals = {total.option_id: total.votes for total in polls.totals(poll.id)}
        return PollDTO(
            id=poll.id, group_id=poll.group_id, question=poll.question, state=poll.state,
            created_by=poll.created_by, created_at=poll.created_at, closed_at=poll.closed_at,
            options=[PollOptionDTO(id=option.id, position=option.position, text=option.text,
                                   votes=totals.get(option.id, 0)) for option in options],
            total_votes=sum(totals.values()), my_vote=polls.my_vote(poll.id, user.id),
        )


def _name(user: User) -> str:
    return user.display_name or "Member"
