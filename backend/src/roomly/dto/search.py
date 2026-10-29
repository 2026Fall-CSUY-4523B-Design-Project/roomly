"""DTOs for Search and Ranking (§8.1.2.5, R-3.1, R-3.2) and the user's saved inputs."""

import datetime as dt
from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import UUID

from roomly.dto.base import rule
from roomly.dto.listing import Borough
from roomly.entity import CommuteDestination, SavedSearch

SortOrder = Literal["newest", "rent_asc", "rent_desc"]
TravelMode = Literal["transit", "walk", "bike", "drive"]


@dataclass(frozen=True)
class SearchCriteria:
    """Hard constraints. A listing whose value is Unknown fails any active constraint on it."""

    min_rent_cents: int | None = rule(default=None, ge=0)
    max_rent_cents: int | None = rule(default=None, ge=0)
    boroughs: list[Borough] = rule(default_factory=list, unique=True)
    min_bedrooms: int | None = rule(default=None, ge=0, le=20)
    max_bedrooms: int | None = rule(default=None, ge=0, le=20)
    min_area_sqft: int | None = rule(default=None, ge=1)
    move_in_from: dt.date | None = None
    move_in_to: dt.date | None = None
    amenities: list[str] = rule(default_factory=list, max_items=20, unique=True)
    no_broker_fee: bool = False
    # map viewport: give all four or none
    south: float | None = rule(default=None, ge=-90, le=90)
    west: float | None = rule(default=None, ge=-180, le=180)
    north: float | None = rule(default=None, ge=-90, le=90)
    east: float | None = rule(default=None, ge=-180, le=180)

    def check(self) -> list[tuple[str, str]]:
        problems = []
        for low, high in (("min_rent_cents", "max_rent_cents"), ("min_bedrooms", "max_bedrooms"),
                          ("move_in_from", "move_in_to"), ("south", "north"), ("west", "east")):
            a, b = getattr(self, low), getattr(self, high)
            if a is not None and b is not None and a > b:
                problems.append((high, f"{high} must not be less than {low}"))
        box = (self.south, self.west, self.north, self.east)
        if any(v is not None for v in box) and any(v is None for v in box):
            problems.append(("south", "a map viewport needs south, west, north and east"))
        return problems


@dataclass(frozen=True)
class SavedSearchRequest:
    name: str = rule(min_len=1, max_len=80)
    criteria: SearchCriteria = field(default_factory=SearchCriteria)
    weights: dict[str, float] = field(default_factory=dict)   # used by ranking (Sprint 4)
    alerts_enabled: bool = True


@dataclass(frozen=True)
class SavedSearchDTO:
    id: UUID
    name: str
    criteria: dict[str, Any]
    weights: dict[str, Any]
    alerts_enabled: bool
    created_at: dt.datetime
    updated_at: dt.datetime

    @classmethod
    def from_entity(cls, s: SavedSearch) -> SavedSearchDTO:
        return cls(id=s.id, name=s.name, criteria=s.criteria, weights=s.weights, alerts_enabled=s.alerts_enabled,
                   created_at=s.created_at, updated_at=s.updated_at)


@dataclass(frozen=True)
class CommuteDestinationRequest:
    label: str = rule(min_len=1, max_len=60)
    address: str | None = rule(default=None, min_len=1, max_len=200)
    latitude: float | None = rule(default=None, ge=-90, le=90)
    longitude: float | None = rule(default=None, ge=-180, le=180)
    mode: TravelMode = "transit"

    def check(self) -> list[tuple[str, str]]:
        if (self.latitude is None) != (self.longitude is None):
            return [("longitude", "latitude and longitude must be given together")]
        if self.latitude is None and self.address is None:
            return [("address", "give an address or coordinates")]
        return []


@dataclass(frozen=True)
class CommuteDestinationDTO:
    id: UUID
    label: str
    address: str | None
    latitude: float | None
    longitude: float | None
    mode: str
    created_at: dt.datetime

    @classmethod
    def from_entity(cls, d: CommuteDestination) -> CommuteDestinationDTO:
        return cls(id=d.id, label=d.label, address=d.address, latitude=d.latitude, longitude=d.longitude,
                   mode=d.mode, created_at=d.created_at)
