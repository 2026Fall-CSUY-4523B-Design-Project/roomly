"""ComparisonService (§9.1 control class): side-by-side comparison of 2-4 listings (R-4).

Best-value highlighting only ever looks at known values (an Unknown is never "best"), needs
at least two of them, and states its direction. Saved comparisons keep a snapshot of each
listing so later changes are reported instead of silently replacing what was compared.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import psycopg

from roomly.db import Database
from roomly.dto.common import PersonRef
from roomly.dto.comparison import (
    ComparisonCell,
    ComparisonDTO,
    ComparisonRow,
    ComparisonSummaryDTO,
    ComparisonTableDTO,
    Direction,
    ListingChangeDTO,
    PreviewRequest,
    SaveComparisonRequest,
    ShareRequest,
)
from roomly.dto.listing import ListingSummaryDTO
from roomly.entity import Comparison, Listing, User
from roomly.mapper import ComparisonMapper, ListingMapper, UserMapper
from roomly.service.access import require_member
from roomly.service.errors import Conflict, Forbidden, Invalid, NotFound
from roomly.service.listing_service import json_safe, price_per_sqft

logger = logging.getLogger(__name__)

MIN_LISTINGS, MAX_LISTINGS = 2, 4
COMMUTE_NOTE = "Commute estimates are not available yet (routing arrives with Search and Ranking in Sprint 4)."


@dataclass(frozen=True)
class _Attr:
    key: str
    label: str
    direction: Direction | None
    get: Callable[[Listing], Any]
    formula: str | None = None


def _address(listing: Listing) -> str | None:
    if listing.address_line is None:
        return None
    return f"{listing.address_line}, unit {listing.unit}" if listing.unit else listing.address_line


_ATTRS: list[_Attr] = [
    _Attr("advertised_rent_cents", "Advertised monthly rent", "lower", lambda x: x.advertised_rent_cents),
    _Attr("net_effective_rent_cents", "Net-effective monthly rent", "lower", lambda x: x.net_effective_rent_cents),
    _Attr("broker_fee_cents", "Broker fee", "lower", lambda x: x.broker_fee_cents),
    _Attr("monthly_fees_cents", "Other monthly fees", "lower", lambda x: x.monthly_fees_cents),
    _Attr("price_per_sqft_cents", "Price per sq ft", "lower",
          lambda x: price_per_sqft(x.advertised_rent_cents, x.area_sqft).value,
          formula=price_per_sqft(None, None).formula),
    _Attr("borough", "Borough", None, lambda x: x.borough),
    _Attr("address", "Address", None, _address),
    _Attr("bedrooms", "Bedrooms", None, lambda x: x.bedrooms),
    _Attr("bathrooms", "Bathrooms", None, lambda x: None if x.bathrooms is None else float(x.bathrooms)),
    _Attr("area_sqft", "Area (sq ft)", "higher", lambda x: x.area_sqft),
    _Attr("move_in_date", "Move-in date", None, lambda x: x.move_in_date),
    _Attr("amenities", "Amenities", None, lambda x: list(x.amenities) or None),  # none reported = Unknown
    _Attr("commute", "Commute", None, lambda x: None),
]

SNAPSHOT_FIELDS = ("status", "advertised_rent_cents", "net_effective_rent_cents", "broker_fee_cents",
                   "monthly_fees_cents", "bedrooms", "bathrooms", "area_sqft", "move_in_date", "amenities",
                   "borough", "address_line", "unit", "availability")


def snapshot(listing: Listing) -> dict[str, Any]:
    return json_safe({k: getattr(listing, k) for k in SNAPSHOT_FIELDS})


def _row(attr: _Attr, listings: list[Listing]) -> ComparisonRow:
    values = [attr.get(x) for x in listings]
    best: set[int] = set()
    known = [(i, v) for i, v in enumerate(values) if v is not None]
    if attr.direction is not None and len(known) >= 2 and len({v for _, v in known}) > 1:
        target = min(v for _, v in known) if attr.direction == "lower" else max(v for _, v in known)
        best = {i for i, v in known if v == target}
    cells = [ComparisonCell(listing_id=x.id, value=v, known=v is not None, best=i in best)
             for i, (x, v) in enumerate(zip(listings, values, strict=True))]
    return ComparisonRow(key=attr.key, label=attr.label, direction=attr.direction, formula=attr.formula, cells=cells)


def build_table(listings: list[Listing]) -> ComparisonTableDTO:
    return ComparisonTableDTO(listings=[ListingSummaryDTO.from_entity(x) for x in listings],
                              rows=[_row(a, listings) for a in _ATTRS], notes=[COMMUTE_NOTE])


class ComparisonService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def preview(self, req: PreviewRequest) -> ComparisonTableDTO:
        with self.db.transaction() as conn:
            return build_table(self._load_comparable(conn, req.listing_ids))

    def save(self, user: User, req: SaveComparisonRequest) -> ComparisonDTO:
        with self.db.transaction() as conn:
            if req.group_id is not None:
                require_member(conn, user, req.group_id)
            listings = self._load_comparable(conn, req.listing_ids)
            comparisons = ComparisonMapper(conn)
            comparison = comparisons.insert(user.id, req.group_id, req.title)
            for position, listing in enumerate(listings, start=1):
                comparisons.add_listing(comparison.id, position, listing.id, snapshot(listing))
            dto = self._dto(conn, comparison)
        logger.info("comparison saved comparison=%s group=%s by=%s", comparison.id, req.group_id, user.id)
        return dto

    def get(self, user: User, comparison_id: UUID) -> ComparisonDTO:
        with self.db.transaction() as conn:
            comparison = self._visible(conn, user, comparison_id)
            return self._dto(conn, comparison)

    def share(self, user: User, comparison_id: UUID, req: ShareRequest) -> ComparisonDTO:
        with self.db.transaction() as conn:
            comparison = self._visible(conn, user, comparison_id)
            if comparison.saved_by != user.id:
                raise Forbidden("only the member who saved a comparison can share it")
            if comparison.group_id is not None:
                raise Conflict("this comparison is already shared with a group")
            require_member(conn, user, req.group_id)
            shared = ComparisonMapper(conn).share(comparison.id, req.group_id)
            assert shared is not None
            dto = self._dto(conn, shared)
        logger.info("comparison shared comparison=%s group=%s", comparison_id, req.group_id)
        return dto

    def list_for_group(self, user: User, group_id: UUID) -> list[ComparisonSummaryDTO]:
        with self.db.transaction() as conn:
            require_member(conn, user, group_id)
            return [self._summary(conn, c) for c in ComparisonMapper(conn).list_for_group(group_id)]

    def list_personal(self, user: User) -> list[ComparisonSummaryDTO]:
        with self.db.transaction() as conn:
            return [self._summary(conn, c) for c in ComparisonMapper(conn).list_personal(user.id)]

    # --- helpers ---------------------------------------------------------------------

    def _load_comparable(self, conn: psycopg.Connection, ids: list[UUID]) -> list[Listing]:
        """§8.1.2.6 alt. flow 1: 2-4 distinct, existing, searchable listings, in the order given."""
        if not MIN_LISTINGS <= len(ids) <= MAX_LISTINGS or len(set(ids)) != len(ids):
            raise Invalid(f"choose {MIN_LISTINGS} to {MAX_LISTINGS} different listings")
        found = {x.id: x for x in ListingMapper(conn).find_many(ids)}
        missing = [str(i) for i in ids if i not in found]
        if missing:
            raise Invalid("listings not found: " + ", ".join(missing))
        unavailable = [f"{i} ({found[i].status})" for i in ids if found[i].status != "searchable"]
        if unavailable:
            raise Invalid("listings not available for comparison: " + ", ".join(unavailable))
        return [found[i] for i in ids]

    def _visible(self, conn: psycopg.Connection, user: User, comparison_id: UUID) -> Comparison:
        comparison = ComparisonMapper(conn).find(comparison_id)
        if comparison is None:
            raise NotFound("comparison not found")
        if comparison.group_id is None:
            if comparison.saved_by != user.id:
                raise NotFound("comparison not found")  # personal: invisible to everyone else
        else:
            require_member(conn, user, comparison.group_id)
        return comparison

    def _summary(self, conn: psycopg.Connection, c: Comparison) -> ComparisonSummaryDTO:
        items = ComparisonMapper(conn).items(c.id)
        return ComparisonSummaryDTO(id=c.id, title=c.title, group_id=c.group_id, saved_by=self._person(conn, c.saved_by),
                                    saved_at=c.saved_at, shared_at=c.shared_at, listing_ids=[i.listing_id for i in items])

    def _dto(self, conn: psycopg.Connection, c: Comparison) -> ComparisonDTO:
        summary = self._summary(conn, c)
        items = ComparisonMapper(conn).items(c.id)
        current = {x.id: x for x in ListingMapper(conn).find_many([i.listing_id for i in items])}
        listings = [current[i.listing_id] for i in items]
        changes = []
        for item, listing in zip(items, listings, strict=True):
            now = snapshot(listing)
            diff = [k for k in SNAPSHOT_FIELDS if item.snapshot.get(k) != now.get(k)]
            state = "removed" if listing.status == "removed" else ("changed" if diff else "unchanged")
            changes.append(ListingChangeDTO(listing_id=listing.id, state=state, changed_fields=diff))
        return ComparisonDTO(**vars(summary), table=build_table(listings), changes=changes,
                             stale=any(ch.state != "unchanged" for ch in changes))

    def _person(self, conn: psycopg.Connection, user_id: UUID | None) -> PersonRef:
        user = UserMapper(conn).find(user_id) if user_id else None
        if user is None:
            return PersonRef.of(None, None, True)
        return PersonRef.of(user.id, user.display_name, user.deleted_at is not None)
