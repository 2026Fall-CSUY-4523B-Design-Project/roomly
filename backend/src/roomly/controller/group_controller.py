"""Group Management use case (§8.1.2.2): /groups and /invitations."""

from uuid import UUID

from fastapi import APIRouter

from roomly.controller.base import CurrentUser, Svc
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


@router.post("/groups", status_code=201, summary="Create a group; you become its owner")
def create_group(req: CreateGroupRequest, user: CurrentUser, svc: Svc) -> GroupDetailDTO:
    return svc.group.create(user, req)


@router.get("/groups", summary="Groups you are a current member of")
def list_groups(user: CurrentUser, svc: Svc) -> list[GroupSummaryDTO]:
    return svc.group.list_mine(user)


@router.get("/groups/{group_id}", summary="A group and its current members")
def get_group(group_id: UUID, user: CurrentUser, svc: Svc) -> GroupDetailDTO:
    return svc.group.get(user, group_id)


@router.post("/groups/{group_id}/invitations", status_code=201, summary="Invite someone by email (owner)")
def invite(group_id: UUID, req: InviteRequest, user: CurrentUser, svc: Svc) -> InvitationDTO:
    return svc.group.invite(user, group_id, req)


@router.get("/groups/{group_id}/invitations", summary="Invitations this group has sent")
def list_group_invitations(group_id: UUID, user: CurrentUser, svc: Svc) -> list[InvitationDTO]:
    return svc.group.list_invitations(user, group_id)


@router.post("/groups/{group_id}/leave", status_code=204, summary="Leave a group")
def leave_group(group_id: UUID, user: CurrentUser, svc: Svc) -> None:
    svc.group.leave(user, group_id)


@router.post("/groups/{group_id}/transfer", summary="Hand ownership to another member (owner)")
def transfer_ownership(group_id: UUID, req: TransferOwnershipRequest, user: CurrentUser, svc: Svc) -> GroupDetailDTO:
    return svc.group.transfer(user, group_id, req)


@router.delete("/groups/{group_id}/members/{user_id}", status_code=204, summary="Remove a member (owner)")
def remove_member(group_id: UUID, user_id: UUID, user: CurrentUser, svc: Svc) -> None:
    svc.group.remove_member(user, group_id, user_id)


@router.get("/invitations", summary="Pending invitations addressed to you")
def incoming_invitations(user: CurrentUser, svc: Svc) -> list[IncomingInvitationDTO]:
    return svc.group.incoming(user)


@router.post("/invitations/{invitation_id}/accept", status_code=201, summary="Accept an invitation and join")
def accept_invitation(invitation_id: UUID, user: CurrentUser, svc: Svc) -> GroupDetailDTO:
    return svc.group.accept(user, invitation_id)


@router.post("/invitations/{invitation_id}/decline", status_code=204, summary="Decline an invitation")
def decline_invitation(invitation_id: UUID, user: CurrentUser, svc: Svc) -> None:
    svc.group.decline(user, invitation_id)
