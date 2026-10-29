"""DTOs for Listing Administration (§8.1.2.4, R-2.3, R-2.4)."""

import datetime as dt
from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import UUID

from roomly.dto.base import rule
from roomly.dto.listing import ListingSummaryDTO
from roomly.entity import ListingSource

SourceKind = Literal["feed", "url", "manual"]


@dataclass(frozen=True)
class CreateSourceRequest:
    name: str = rule(min_len=1, max_len=80)
    kind: SourceKind = "feed"
    enabled: bool = True
    is_synthetic: bool = True
    config: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class UpdateSourceRequest:
    """Only the fields present are changed."""

    name: str | None = rule(default=None, min_len=1, max_len=80)
    enabled: bool | None = None
    config: dict[str, Any] | None = None


@dataclass(frozen=True)
class SourceDTO:
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


@dataclass(frozen=True)
class DuplicateSideDTO:
    record_id: UUID
    original_url: str | None
    collected_at: dt.datetime
    listing: ListingSummaryDTO | None
    listing_status: str | None


@dataclass(frozen=True)
class DuplicateDTO:
    """A pair of records that may describe the same unit, waiting for (or after) review."""

    id: UUID
    confidence: float
    status: str
    created_at: dt.datetime
    reviewed_at: dt.datetime | None
    a: DuplicateSideDTO
    b: DuplicateSideDTO


@dataclass(frozen=True)
class ResolveReportRequest:
    status: Literal["resolved", "dismissed"]
