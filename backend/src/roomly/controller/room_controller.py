"""Group Discussion use case (§8.1.2.7): room messages, reactions and polls."""

import datetime as dt

from fastapi_reborn import APIRouter, Request

from roomly.controller.base import (
    BEARER,
    current_user,
    paging,
    path_uuid,
    query_uuid,
    read,
    run,
    services,
)
from roomly.dto.base import body, parse, returns
from roomly.dto.room import (
    CreatePollRequest,
    MessageCursor,
    MessageDTO,
    PollDTO,
    PostMessageRequest,
    ReactionCountDTO,
    ReactionRequest,
    VoteRequest,
)

router = APIRouter(tags=["rooms"])


@router.get("/groups/{group_id}/messages", summary="Room messages, newest first", security=BEARER,
            responses=returns(list[MessageDTO]))
async def list_messages(request: Request, group_id: str, listing_id: str | None = None,
                        comparison_id: str | None = None, before: str | None = None,
                        limit: int = 50) -> list[MessageDTO]:
    """Filter to one thread with ``listing_id`` or ``comparison_id``; page back with ``before`` (ISO time)."""
    user = await current_user(request)
    limit, _ = paging(limit, 0)
    cursor: dt.datetime | None = None
    if before is not None:
        cursor = parse(MessageCursor, {"before": before}, loc=("query",)).before
    return await run(services(request).room.list_messages, user, path_uuid(group_id, "group_id"),
                     listing_id=query_uuid(listing_id, "listing_id"),
                     comparison_id=query_uuid(comparison_id, "comparison_id"), before=cursor, limit=limit)


@router.post("/groups/{group_id}/messages", status_code=201, summary="Post a message to the room", security=BEARER,
             request_body=body(PostMessageRequest), responses=returns(MessageDTO, 201))
async def post_message(request: Request, group_id: str) -> MessageDTO:
    user = await current_user(request)
    req = await read(request, PostMessageRequest)
    return await run(services(request).room.post_message, user, path_uuid(group_id, "group_id"), req)


@router.put("/messages/{message_id}/reaction", summary="Set your one reaction on a message", security=BEARER,
            request_body=body(ReactionRequest), responses=returns(list[ReactionCountDTO]))
async def react(request: Request, message_id: str) -> list[ReactionCountDTO]:
    user = await current_user(request)
    req = await read(request, ReactionRequest)
    return await run(services(request).room.react, user, path_uuid(message_id, "message_id"), req)


@router.delete("/messages/{message_id}/reaction", summary="Remove your reaction", security=BEARER,
               responses=returns(list[ReactionCountDTO]))
async def unreact(request: Request, message_id: str) -> list[ReactionCountDTO]:
    user = await current_user(request)
    return await run(services(request).room.unreact, user, path_uuid(message_id, "message_id"))


@router.post("/groups/{group_id}/polls", status_code=201, summary="Create a poll with 2-4 options", security=BEARER,
             request_body=body(CreatePollRequest), responses=returns(PollDTO, 201))
async def create_poll(request: Request, group_id: str) -> PollDTO:
    user = await current_user(request)
    req = await read(request, CreatePollRequest)
    return await run(services(request).room.create_poll, user, path_uuid(group_id, "group_id"), req)


@router.get("/groups/{group_id}/polls", summary="Polls in a room", security=BEARER, responses=returns(list[PollDTO]))
async def list_polls(request: Request, group_id: str) -> list[PollDTO]:
    user = await current_user(request)
    return await run(services(request).room.list_polls, user, path_uuid(group_id, "group_id"))


@router.get("/polls/{poll_id}", summary="A poll with current totals", security=BEARER, responses=returns(PollDTO))
async def get_poll(request: Request, poll_id: str) -> PollDTO:
    user = await current_user(request)
    return await run(services(request).room.get_poll, user, path_uuid(poll_id, "poll_id"))


@router.put("/polls/{poll_id}/vote", summary="Cast or change your vote", security=BEARER,
            request_body=body(VoteRequest), responses=returns(PollDTO))
async def vote(request: Request, poll_id: str) -> PollDTO:
    user = await current_user(request)
    req = await read(request, VoteRequest)
    return await run(services(request).room.vote, user, path_uuid(poll_id, "poll_id"), req)


@router.post("/polls/{poll_id}/close", summary="Close voting (creator or owner)", security=BEARER,
             responses=returns(PollDTO))
async def close_poll(request: Request, poll_id: str) -> PollDTO:
    user = await current_user(request)
    return await run(services(request).room.close_poll, user, path_uuid(poll_id, "poll_id"))

