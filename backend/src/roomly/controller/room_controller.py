"""Group Discussion use case (§8.1.2.7): room messages, reactions and polls."""

import datetime as dt
from uuid import UUID

from fastapi import APIRouter

from roomly.controller.base import CurrentUser, Limit, Svc
from roomly.dto.room import (
    CreatePollRequest,
    MessageDTO,
    PollDTO,
    PostMessageRequest,
    ReactionCountDTO,
    ReactionRequest,
    VoteRequest,
)

router = APIRouter(tags=["rooms"])


@router.get("/groups/{group_id}/messages", summary="Room messages, newest first")
def list_messages(group_id: UUID, user: CurrentUser, svc: Svc, listing_id: UUID | None = None,
                  comparison_id: UUID | None = None, before: dt.datetime | None = None,
                  limit: Limit = 50) -> list[MessageDTO]:
    """Filter to one thread with ``listing_id`` or ``comparison_id``; page back with ``before`` (ISO time)."""
    return svc.room.list_messages(user, group_id, listing_id=listing_id, comparison_id=comparison_id,
                                  before=before, limit=limit)


@router.post("/groups/{group_id}/messages", status_code=201, summary="Post a message to the room")
def post_message(group_id: UUID, req: PostMessageRequest, user: CurrentUser, svc: Svc) -> MessageDTO:
    return svc.room.post_message(user, group_id, req)


@router.put("/messages/{message_id}/reaction", summary="Set your one reaction on a message")
def react(message_id: UUID, req: ReactionRequest, user: CurrentUser, svc: Svc) -> list[ReactionCountDTO]:
    return svc.room.react(user, message_id, req)


@router.delete("/messages/{message_id}/reaction", summary="Remove your reaction")
def unreact(message_id: UUID, user: CurrentUser, svc: Svc) -> list[ReactionCountDTO]:
    return svc.room.unreact(user, message_id)


@router.post("/groups/{group_id}/polls", status_code=201, summary="Create a poll with 2-4 options")
def create_poll(group_id: UUID, req: CreatePollRequest, user: CurrentUser, svc: Svc) -> PollDTO:
    return svc.room.create_poll(user, group_id, req)


@router.get("/groups/{group_id}/polls", summary="Polls in a room")
def list_polls(group_id: UUID, user: CurrentUser, svc: Svc) -> list[PollDTO]:
    return svc.room.list_polls(user, group_id)


@router.get("/polls/{poll_id}", summary="A poll with current totals")
def get_poll(poll_id: UUID, user: CurrentUser, svc: Svc) -> PollDTO:
    return svc.room.get_poll(user, poll_id)


@router.put("/polls/{poll_id}/vote", summary="Cast or change your vote")
def vote(poll_id: UUID, req: VoteRequest, user: CurrentUser, svc: Svc) -> PollDTO:
    return svc.room.vote(user, poll_id, req)


@router.post("/polls/{poll_id}/close", summary="Close voting (creator or owner)")
def close_poll(poll_id: UUID, user: CurrentUser, svc: Svc) -> PollDTO:
    return svc.room.close_poll(user, poll_id)
