"""Group Management use case (§8.1.2.2): /groups and /invitations."""

from fastapi_reborn import APIRouter, Request

from roomly.controller.base import BEARER, current_user, path_uuid, read, run, services
from roomly.dto.base import body, returns
from roomly.dto.group import (
    CreateGroupRequest,
    GroupDetailDTO,
    GroupSummaryDTO,
    IncomingInvitationDTO,
    InvitationDTO,
    InviteRequest,
    TransferOwnershipRequest,
)

router = APIRouter(tags=["groups"])


@router.post("/groups", status_code=201, summary="Create a group; you become its owner", security=BEARER,
             request_body=body(CreateGroupRequest), responses=returns(GroupDetailDTO, 201))
async def create_group(request: Request) -> GroupDetailDTO:
    user = await current_user(request)
    req = await read(request, CreateGroupRequest)
    return await run(services(request).group.create, user, req)


@router.get("/groups", summary="Groups you are a current member of", security=BEARER,
            responses=returns(list[GroupSummaryDTO]))
async def list_groups(request: Request) -> list[GroupSummaryDTO]:
    user = await current_user(request)
    return await run(services(request).group.list_mine, user)


@router.get("/groups/{group_id}", summary="A group and its current members", security=BEARER,
            responses=returns(GroupDetailDTO))
async def get_group(request: Request, group_id: str) -> GroupDetailDTO:
    user = await current_user(request)
    return await run(services(request).group.get, user, path_uuid(group_id, "group_id"))


@router.post("/groups/{group_id}/invitations", status_code=201, summary="Invite someone by email (owner)",
             security=BEARER, request_body=body(InviteRequest), responses=returns(InvitationDTO, 201))
async def invite(request: Request, group_id: str) -> InvitationDTO:
    user = await current_user(request)
    req = await read(request, InviteRequest)
    return await run(services(request).group.invite, user, path_uuid(group_id, "group_id"), req)


@router.get("/groups/{group_id}/invitations", summary="Invitations this group has sent", security=BEARER,
            responses=returns(list[InvitationDTO]))
async def list_group_invitations(request: Request, group_id: str) -> list[InvitationDTO]:
    user = await current_user(request)
    return await run(services(request).group.list_invitations, user, path_uuid(group_id, "group_id"))


@router.post("/groups/{group_id}/leave", status_code=204, summary="Leave a group", security=BEARER)
async def leave_group(request: Request, group_id: str) -> None:
    user = await current_user(request)
    await run(services(request).group.leave, user, path_uuid(group_id, "group_id"))


@router.post("/groups/{group_id}/transfer", summary="Hand ownership to another member (owner)", security=BEARER,
             request_body=body(TransferOwnershipRequest), responses=returns(GroupDetailDTO))
async def transfer_ownership(request: Request, group_id: str) -> GroupDetailDTO:
    user = await current_user(request)
    req = await read(request, TransferOwnershipRequest)
    return await run(services(request).group.transfer, user, path_uuid(group_id, "group_id"), req)


@router.delete("/groups/{group_id}/members/{user_id}", status_code=204, summary="Remove a member (owner)",
               security=BEARER)
async def remove_member(request: Request, group_id: str, user_id: str) -> None:
    user = await current_user(request)
    await run(services(request).group.remove_member, user, path_uuid(group_id, "group_id"),
              path_uuid(user_id, "user_id"))


@router.get("/invitations", summary="Pending invitations addressed to you", security=BEARER,
            responses=returns(list[IncomingInvitationDTO]))
async def incoming_invitations(request: Request) -> list[IncomingInvitationDTO]:
    user = await current_user(request)
    return await run(services(request).group.incoming, user)


@router.post("/invitations/{invitation_id}/accept", status_code=201, summary="Accept an invitation and join",
             security=BEARER, responses=returns(GroupDetailDTO, 201))
async def accept_invitation(request: Request, invitation_id: str) -> GroupDetailDTO:
    user = await current_user(request)
    return await run(services(request).group.accept, user, path_uuid(invitation_id, "invitation_id"))


@router.post("/invitations/{invitation_id}/decline", status_code=204, summary="Decline an invitation",
             security=BEARER)
async def decline_invitation(request: Request, invitation_id: str) -> None:
    user = await current_user(request)
    await run(services(request).group.decline, user, path_uuid(invitation_id, "invitation_id"))
