"""DTOs for Comparison (§8.1.2.6, R-4)."""

import datetime as dt
from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID

from roomly.dto.base import rule
from roomly.dto.common import PersonRef
from roomly.dto.listing import ListingSummaryDTO

Direction = Literal["lower", "higher"]
ChangeState = Literal["unchanged", "changed", "removed"]


@dataclass(frozen=True)
class PreviewRequest:
    listing_ids: list[UUID] = rule(min_items=2, max_items=4, unique=True)


@dataclass(frozen=True)
class SaveComparisonRequest:
    """Save a comparison; with ``group_id`` it is also shared to that group's room."""

    listing_ids: list[UUID] = rule(min_items=2, max_items=4, unique=True)
    group_id: UUID | None = None
    title: str | None = rule(default=None, min_len=1, max_len=120)


@dataclass(frozen=True)
class ShareRequest:
    group_id: UUID


@dataclass(frozen=True)
class ComparisonCell:
    listing_id: UUID
    value: Any
    known: bool
    best: bool


@dataclass(frozen=True)
class ComparisonRow:
    """One aligned attribute. ``direction`` says which way is better when ``best`` is highlighted."""

    key: str
    label: str
    direction: Direction | None
    formula: str | None
    cells: list[ComparisonCell]


@dataclass(frozen=True)
class ComparisonTableDTO:
    listings: list[ListingSummaryDTO]
    rows: list[ComparisonRow]
    notes: list[str]


@dataclass(frozen=True)
class ListingChangeDTO:
    """How a referenced listing differs from when the comparison was saved (R-4.5)."""

    listing_id: UUID
    state: ChangeState
    changed_fields: list[str]


@dataclass(frozen=True)
class ComparisonSummaryDTO:
    id: UUID
    title: str | None
    group_id: UUID | None
    saved_by: PersonRef
    saved_at: dt.datetime
    shared_at: dt.datetime | None
    listing_ids: list[UUID]


@dataclass(frozen=True)
class ComparisonDTO(ComparisonSummaryDTO):
    table: ComparisonTableDTO
    changes: list[ListingChangeDTO]
    stale: bool
