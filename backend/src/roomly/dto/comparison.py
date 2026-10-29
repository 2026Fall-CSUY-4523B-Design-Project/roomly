"""DTOs for Comparison (§8.1.2.6, R-4)."""

import datetime as dt
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import Field

from roomly.dto.base import DTO, Distinct
from roomly.dto.common import PersonRef
from roomly.dto.listing import ListingSummaryDTO

Direction = Literal["lower", "higher"]
ChangeState = Literal["unchanged", "changed", "removed"]


class PreviewRequest(DTO):
    listing_ids: Annotated[list[UUID], Distinct] = Field(min_length=2, max_length=4)


class SaveComparisonRequest(DTO):
    """Save a comparison; with ``group_id`` it is also shared to that group's room."""

    listing_ids: Annotated[list[UUID], Distinct] = Field(min_length=2, max_length=4)
    group_id: UUID | None = None
    title: str | None = Field(default=None, min_length=1, max_length=120)


class ShareRequest(DTO):
    group_id: UUID


class ComparisonCell(DTO):
    listing_id: UUID
    value: Any
    known: bool
    best: bool


class ComparisonRow(DTO):
    """One aligned attribute. ``direction`` says which way is better when ``best`` is highlighted."""

    key: str
    label: str
    direction: Direction | None
    formula: str | None
    cells: list[ComparisonCell]


class ComparisonTableDTO(DTO):
    listings: list[ListingSummaryDTO]
    rows: list[ComparisonRow]
    notes: list[str]


class ListingChangeDTO(DTO):
    """How a referenced listing differs from when the comparison was saved (R-4.5)."""

    listing_id: UUID
    state: ChangeState
    changed_fields: list[str]


class ComparisonSummaryDTO(DTO):
    id: UUID
    title: str | None
    group_id: UUID | None
    saved_by: PersonRef
    saved_at: dt.datetime
    shared_at: dt.datetime | None
    listing_ids: list[UUID]


class ComparisonDTO(ComparisonSummaryDTO):
    table: ComparisonTableDTO
    changes: list[ListingChangeDTO]
    stale: bool
