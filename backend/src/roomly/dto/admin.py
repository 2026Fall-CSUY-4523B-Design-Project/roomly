"""DTOs for Listing Administration (§8.1.2.4, R-2.3, R-2.4)."""

import datetime as dt
from typing import Any, Literal
from uuid import UUID

from pydantic import Field, StrictBool

from roomly.dto.base import DTO
from roomly.dto.listing import ListingSummaryDTO
from roomly.entity import ListingSource

SourceKind = Literal["feed", "url", "manual"]


class CreateSourceRequest(DTO):
    name: str = Field(min_length=1, max_length=80)
    kind: SourceKind = "feed"
    enabled: StrictBool = True
    is_synthetic: StrictBool = True
    config: dict[str, Any] = Field(default_factory=dict)


class UpdateSourceRequest(DTO):
    """Only the fields present are changed."""

    name: str | None = Field(default=None, min_length=1, max_length=80)
    enabled: StrictBool | None = None
    config: dict[str, Any] | None = None


class SourceDTO(DTO):
    id: UUID
    name: str
    kind: str
    enabled: bool
    is_synthetic: bool
    config: dict[str, Any]
    last_run_at: dt.datetime | None
    last_error: str | None
    created_at: dt.datetime

    @classmethod
    def from_entity(cls, s: ListingSource) -> SourceDTO:
        return cls(id=s.id, name=s.name, kind=s.kind, enabled=s.enabled, is_synthetic=s.is_synthetic,
                   config=s.config, last_run_at=s.last_run_at, last_error=s.last_error, created_at=s.created_at)


class DuplicateSideDTO(DTO):
    record_id: UUID
    original_url: str | None
    collected_at: dt.datetime
    listing: ListingSummaryDTO | None
    listing_status: str | None


class DuplicateDTO(DTO):
    """A pair of records that may describe the same unit, waiting for (or after) review."""

    id: UUID
    confidence: float
    status: str
    created_at: dt.datetime
    reviewed_at: dt.datetime | None
    a: DuplicateSideDTO
    b: DuplicateSideDTO


class ResolveReportRequest(DTO):
    status: Literal["resolved", "dismissed"]
