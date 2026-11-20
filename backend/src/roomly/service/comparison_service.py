"""ComparisonService (§9.1 control class): side-by-side comparison of 2-4 listings (R-4).

Best-value highlighting only ever looks at known values (an Unknown is never "best"), needs
at least two of them, and states its direction. Saved comparisons keep a snapshot of each
listing so later changes are reported instead of silently replacing what was compared.
"""

import datetime as dt
from decimal import Decimal
from typing import Any
from uuid import UUID

from roomly.db import Database, Tx
from roomly.dto.common import PersonRef
from roomly.dto.comparison import (
    ChangeState,
    ComparisonCell,
    ComparisonDTO,
    ComparisonRow,
    ComparisonSummaryDTO,
    ComparisonTableDTO,
    ListingChangeDTO,
    PreviewRequest,
    SaveComparisonRequest,
    ShareRequest,
)
from roomly.dto.listing import ListingSummaryDTO
from roomly.entity import Comparison, Listing, User
from roomly.mapper.account_mapper import UserMapper
from roomly.mapper.comparison_mapper import ComparisonMapper
from roomly.mapper.listing_mapper import ListingMapper
from roomly.service.access import require_member
from roomly.service.errors import Conflict, Forbidden, NotFound
from roomly.service.listing_service import PRICE_PER_SQFT_FORMULA, price_per_sqft

Direction = str | None

# key, label, better direction, formula
_ROWS: list[tuple[str, str, Direction, str | None]] = [
    ("advertised_rent_cents", "Advertised monthly rent", "lower", None),
    ("net_effective_rent_cents", "Net-effective monthly rent", "lower", None),
    ("broker_fee_cents", "Broker fee", "lower", None),
    ("price_per_sqft_cents", "Price per sq ft", "lower", PRICE_PER_SQFT_FORMULA),
    ("borough", "Borough", None, None),
    ("bedrooms", "Bedrooms", None, None),
    ("area_sqft", "Area (sq ft)", "higher", None),
    ("move_in_date", "Move-in date", None, None),
    ("commute", "Commute", None, None),
]
_SNAPSHOT_FIELDS = [key for key, _, _, _ in _ROWS if key != "commute"]


def _value(listing: Listing, key: str) -> Any:
    if key == "price_per_sqft_cents":
        return price_per_sqft(listing).value
    if key == "commute":
        return None
    return getattr(listing, key)


def _json(value: Any) -> Any:
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def snapshot(listing: Listing) -> dict[str, Any]:
    return {key: _json(_value(listing, key)) for key in _SNAPSHOT_FIELDS}


def _table(listings: list[Listing]) -> ComparisonTableDTO:
    rows = []
    for key, label, direction, formula in _ROWS:
        values = [_value(listing, key) for listing in listings]
        best: set[int] = set()
        known = [(i, v) for i, v in enumerate(values) if v is not None]
        if direction is not None and len(known) >= 2:
            target = min(v for _, v in known) if direction == "lower" else max(v for _, v in known)
            winners = [i for i, v in known if v == target]
            if len(winners) == 1:
                best.add(winners[0])
        rows.append(ComparisonRow(
            key=key, label=label, direction=direction, formula=formula,
            cells=[ComparisonCell(listing_id=listing.id, value=_json(values[i]), known=values[i] is not None,
                                  best=i in best)
                   for i, listing in enumerate(listings)],
        ))
    return ComparisonTableDTO(
        listings=[ListingSummaryDTO.from_entity(listing) for listing in listings],
        rows=rows,
        notes=["Commute estimates are not available yet."],
    )


def _changes(items: list[Any], listings: dict[UUID, Listing]) -> list[ListingChangeDTO]:
    changes = []
    for item in items:
        listing = listings.get(item.listing_id)
        if listing is None or listing.status == "removed":
            changes.append(ListingChangeDTO(listing_id=item.listing_id, state="removed", changed_fields=[]))
            continue
        current = snapshot(listing)
        changed = [key for key in _SNAPSHOT_FIELDS if item.snapshot.get(key) != current.get(key)]
        state: ChangeState = "changed" if changed else "unchanged"
        changes.append(ListingChangeDTO(listing_id=item.listing_id, state=state, changed_fields=changed))
    return changes


class ComparisonService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def preview(self, req: PreviewRequest) -> ComparisonTableDTO:
        with self.db.transaction() as tx:
            listings = self._listings(tx, req.listing_ids)
            return _table(listings)

    def save(self, user: User, req: SaveComparisonRequest) -> ComparisonDTO:
        with self.db.transaction() as tx:
            if req.group_id is not None:
                require_member(tx, req.group_id, user)
            listings = self._listings(tx, req.listing_ids)
            comparison = ComparisonMapper(tx).insert(user.id, req.group_id, req.title)
            for position, listing in enumerate(listings, start=1):
                ComparisonMapper(tx).add_listing(comparison.id, position, listing.id, snapshot(listing))
            return self._dto(tx, comparison)

    def get(self, user: User, comparison_id: UUID) -> ComparisonDTO:
        with self.db.transaction() as tx:
            comparison = self._visible(tx, user, comparison_id)
            return self._dto(tx, comparison)

    def share(self, user: User, comparison_id: UUID, req: ShareRequest) -> ComparisonDTO:
        with self.db.transaction() as tx:
            comparison = ComparisonMapper(tx).find(comparison_id)
            if comparison is None:
                raise NotFound("Comparison not found.")
            if comparison.saved_by != user.id:
                raise Forbidden("Only the person who saved this comparison can share it.")
            if comparison.group_id is not None:
                raise Conflict("This comparison is already shared with a group.")
            require_member(tx, req.group_id, user)
            shared = ComparisonMapper(tx).share(comparison.id, req.group_id)
            assert shared is not None
            return self._dto(tx, shared)

    def list_for_group(self, user: User, group_id: UUID) -> list[ComparisonSummaryDTO]:
        with self.db.transaction() as tx:
            require_member(tx, group_id, user)
            return [self._summary(tx, c) for c in ComparisonMapper(tx).list_for_group(group_id)]

    def list_personal(self, user: User) -> list[ComparisonSummaryDTO]:
        with self.db.transaction() as tx:
            return [self._summary(tx, c) for c in ComparisonMapper(tx).list_personal(user.id)]

    @staticmethod
    def _listings(tx: Tx, listing_ids: list[UUID]) -> list[Listing]:
        found = {listing.id: listing for listing in ListingMapper(tx).find_many(listing_ids)}
        missing = [str(i) for i in listing_ids if i not in found]
        if missing:
            raise NotFound(f"Listing not found: {missing[0]}.")
        return [found[i] for i in listing_ids]

    @staticmethod
    def _visible(tx: Tx, user: User, comparison_id: UUID) -> Comparison:
        comparison = ComparisonMapper(tx).find(comparison_id)
        if comparison is None:
            raise NotFound("Comparison not found.")
        if comparison.group_id is None:
            if comparison.saved_by != user.id:
                raise Forbidden("This comparison belongs to someone else.")
        else:
            require_member(tx, comparison.group_id, user)
        return comparison

    def _dto(self, tx: Tx, comparison: Comparison) -> ComparisonDTO:
        items = ComparisonMapper(tx).items(comparison.id)
        found = {listing.id: listing for listing in ListingMapper(tx).find_many([i.listing_id for i in items])}
        ordered = [found[item.listing_id] for item in items if item.listing_id in found]
        changes = _changes(items, found)
        summary = self._summary(tx, comparison)
        return ComparisonDTO(
            **summary.model_dump(),
            table=_table(ordered), changes=changes,
            stale=any(change.state != "unchanged" for change in changes),
        )

    @staticmethod
    def _summary(tx: Tx, comparison: Comparison) -> ComparisonSummaryDTO:
        items = ComparisonMapper(tx).items(comparison.id)
        author = UserMapper(tx).find(comparison.saved_by) if comparison.saved_by else None
        person = PersonRef.of(
            comparison.saved_by,
            author.display_name if author else None,
            author is None or author.deleted_at is not None,
        )
        return ComparisonSummaryDTO(
            id=comparison.id, title=comparison.title, group_id=comparison.group_id, saved_by=person,
            saved_at=comparison.saved_at, shared_at=comparison.shared_at,
            listing_ids=[item.listing_id for item in items],
        )
