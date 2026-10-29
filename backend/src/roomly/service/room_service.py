"""RoomService (§9.1 control class): messages, reactions and polls in a group room (R-5).

Every action re-checks current membership on the server, so a member who left or was
removed can no longer read, post, react or vote. Realtime push over WebSocket (the 1 s
delivery target) is Sprint 5; clients poll ``GET /groups/{id}/messages`` until then.
"""

import datetime as dt
import logging
from uuid import UUID

import psycopg

from roomly.db import Database
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
from roomly.entity import Membership, Message, Poll, User
from roomly.mapper import (
    ComparisonMapper,
    ListingMapper,
    MessageMapper,
    PollMapper,
    ReactionMapper,
)
from roomly.mapper.room_mapper import MessageView
from roomly.service.access import require_member
from roomly.service.errors import Conflict, Forbidden, Invalid, NotFound
from roomly.service.notification_service import notify_group_message

logger = logging.getLogger(__name__)


class RoomService:
    def __init__(self, db: Database) -> None:
        self.db = db

    # --- messages --------------------------------------------------------------------

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
        with self.db.transaction() as conn:
            require_member(conn, user, group_id)
            rows = MessageMapper(conn).list_thread(group_id, listing_id=listing_id, comparison_id=comparison_id,
                                                   before=before, limit=limit)
            return self._message_dtos(conn, rows, user.id)

    def post_message(self, user: User, group_id: UUID, req: PostMessageRequest) -> MessageDTO:
        with self.db.transaction() as conn:
            group, _ = require_member(conn, user, group_id)
            if req.listing_id is not None and ListingMapper(conn).find(req.listing_id) is None:
                raise Invalid("listing not found")
            if req.comparison_id is not None:
                comparison = ComparisonMapper(conn).find(req.comparison_id)
                if comparison is None or comparison.group_id != group_id:
                    raise Invalid("that comparison is not shared with this group")
            message = MessageMapper(conn).insert(group_id, user.id, req.body, req.listing_id, req.comparison_id)
            notify_group_message(conn, group, message)
            dto = self._message_dto(message, user)
        logger.info("message posted group=%s message=%s", group_id, message.id)  # never the body
        return dto

    def react(self, user: User, message_id: UUID, req: ReactionRequest) -> list[ReactionCountDTO]:
        with self.db.transaction() as conn:
            message = self._message_as_member(conn, user, message_id)
            ReactionMapper(conn).upsert(message.id, user.id, req.emoji)
            return self._reactions(conn, message.id, user.id)

    def unreact(self, user: User, message_id: UUID) -> list[ReactionCountDTO]:
        with self.db.transaction() as conn:
            message = self._message_as_member(conn, user, message_id)
            ReactionMapper(conn).delete(message.id, user.id)
            return self._reactions(conn, message.id, user.id)

    # --- polls -----------------------------------------------------------------------

    def create_poll(self, user: User, group_id: UUID, req: CreatePollRequest) -> PollDTO:
        with self.db.transaction() as conn:
            require_member(conn, user, group_id)
            polls = PollMapper(conn)
            poll = polls.insert(group_id, user.id, req.question)
            for position, text in enumerate(req.options, start=1):
                polls.add_option(poll.id, position, text.strip())
            dto = self._poll_dto(conn, poll, user.id)
        logger.info("poll created group=%s poll=%s options=%d", group_id, poll.id, len(req.options))
        return dto

    def list_polls(self, user: User, group_id: UUID) -> list[PollDTO]:
        with self.db.transaction() as conn:
            require_member(conn, user, group_id)
            return [self._poll_dto(conn, p, user.id) for p in PollMapper(conn).list_for_group(group_id)]

    def get_poll(self, user: User, poll_id: UUID) -> PollDTO:
        with self.db.transaction() as conn:
            poll, _ = self._poll_as_member(conn, user, poll_id, lock=False)
            return self._poll_dto(conn, poll, user.id)

    def vote(self, user: User, poll_id: UUID, req: VoteRequest) -> PollDTO:
        with self.db.transaction() as conn:
            poll, _ = self._poll_as_member(conn, user, poll_id, lock=True)
            if poll.state != "open":
                raise Conflict("this poll is closed")
            polls = PollMapper(conn)
            if req.option_id not in {o.id for o in polls.options(poll.id)}:
                raise Invalid("that option is not part of this poll")
            polls.upsert_vote(poll.id, user.id, req.option_id)
            dto = self._poll_dto(conn, poll, user.id)
        logger.info("vote cast poll=%s user=%s", poll_id, user.id)
        return dto

    def close_poll(self, user: User, poll_id: UUID) -> PollDTO:
        """R-5.4: the creator or the group owner closes voting."""
        with self.db.transaction() as conn:
            poll, membership = self._poll_as_member(conn, user, poll_id, lock=True)
            if poll.created_by != user.id and not membership.is_owner:
                raise Forbidden("only the poll creator or the group owner can close it")
            closed = PollMapper(conn).close(poll.id)
            if closed is None:
                raise Conflict("this poll is already closed")
            dto = self._poll_dto(conn, closed, user.id)
        logger.info("poll closed poll=%s by=%s", poll_id, user.id)
        return dto

    # --- helpers ---------------------------------------------------------------------

    def _message_as_member(self, conn: psycopg.Connection, user: User, message_id: UUID) -> Message:
        message = MessageMapper(conn).find(message_id)
        if message is None:
            raise NotFound("message not found")
        require_member(conn, user, message.group_id)
        return message

    def _poll_as_member(self, conn: psycopg.Connection, user: User, poll_id: UUID, *, lock: bool) -> tuple[Poll, Membership]:
        polls = PollMapper(conn)
        poll = polls.lock(poll_id) if lock else polls.find(poll_id)
        if poll is None:
            raise NotFound("poll not found")
        _, membership = require_member(conn, user, poll.group_id)
        return poll, membership

    def _reactions(self, conn: psycopg.Connection, message_id: UUID, viewer_id: UUID) -> list[ReactionCountDTO]:
        return [ReactionCountDTO(emoji=r.emoji, count=r.count, mine=r.mine)
                for r in ReactionMapper(conn).counts([message_id], viewer_id)]

    def _message_dtos(self, conn: psycopg.Connection, rows: list[MessageView], viewer_id: UUID) -> list[MessageDTO]:
        by_message: dict[UUID, list[ReactionCountDTO]] = {}
        for r in ReactionMapper(conn).counts([m.id for m in rows], viewer_id) if rows else []:
            by_message.setdefault(r.message_id, []).append(ReactionCountDTO(emoji=r.emoji, count=r.count, mine=r.mine))
        return [MessageDTO(id=m.id, group_id=m.group_id, author=PersonRef.of(m.author_id, m.author_name, m.author_deleted),
                           listing_id=m.listing_id, comparison_id=m.comparison_id, body=m.body, sent_at=m.sent_at,
                           reactions=by_message.get(m.id, []))
                for m in rows]

    def _message_dto(self, m: Message, author: User) -> MessageDTO:
        return MessageDTO(id=m.id, group_id=m.group_id, author=PersonRef.of(author.id, author.display_name, False),
                          listing_id=m.listing_id, comparison_id=m.comparison_id, body=m.body, sent_at=m.sent_at,
                          reactions=[])

    def _poll_dto(self, conn: psycopg.Connection, poll: Poll, viewer_id: UUID) -> PollDTO:
        polls = PollMapper(conn)
        totals = {t.option_id: t.votes for t in polls.totals(poll.id)}
        options = [PollOptionDTO(id=o.id, position=o.position, text=o.text, votes=totals.get(o.id, 0))
                   for o in polls.options(poll.id)]
        return PollDTO(id=poll.id, group_id=poll.group_id, question=poll.question, state=poll.state,
                       created_by=poll.created_by, created_at=poll.created_at, closed_at=poll.closed_at,
                       options=options, total_votes=sum(o.votes for o in options),
                       my_vote=polls.my_vote(poll.id, viewer_id))
