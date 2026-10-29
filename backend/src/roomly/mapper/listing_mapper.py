"""SQL for listings, their sources and provenance, duplicate review and data reports."""

import datetime as dt
from dataclasses import dataclass, fields
from typing import Any, Literal
from uuid import UUID

from roomly.entity import (
    DataReport,
    DuplicateCandidate,
    Listing,
    ListingSource,
    PricePoint,
    SourceRecord,
)
from roomly.mapper.base import Mapper, columns, jsonb

_LISTING = columns(Listing)
_SOURCE = columns(ListingSource)
_RECORD = columns(SourceRecord)
_CANDIDATE = columns(DuplicateCandidate)
_REPORT = columns(DataReport)

_LISTING_WRITABLE = frozenset(f.name for f in fields(Listing)) - {"id", "created_at", "updated_at"}
_JSON_COLUMNS = frozenset({"conflicts", "config", "raw_values"})

ListingSort = Literal["newest", "rent_asc", "rent_desc"]
_ORDER: dict[str, str] = {
    "newest": "updated_at DESC, id",
    "rent_asc": "advertised_rent_cents ASC NULLS LAST, id",
    "rent_desc": "advertised_rent_cents DESC NULLS LAST, id",
}


@dataclass(frozen=True)
class ListingFilter:
    """Hard constraints (R-3.1). SQL comparisons with NULL are never true, so a listing whose
    value is Unknown fails every active constraint on that value, exactly as the SSDS requires."""

    min_rent_cents: int | None = None
    max_rent_cents: int | None = None
    boroughs: list[str] | None = None
    min_bedrooms: int | None = None
    max_bedrooms: int | None = None
    min_area_sqft: int | None = None
    move_in_from: dt.date | None = None
    move_in_to: dt.date | None = None
    amenities: list[str] | None = None
    no_broker_fee: bool = False
    # map viewport (R-3.2); listings without coordinates fail it
    south: float | None = None
    west: float | None = None
    north: float | None = None
    east: float | None = None


_CLAUSES: list[tuple[str, str]] = [
    ("min_rent_cents", "advertised_rent_cents >= %(min_rent_cents)s"),
    ("max_rent_cents", "advertised_rent_cents <= %(max_rent_cents)s"),
    ("boroughs", "borough = ANY(%(boroughs)s::text[])"),
    ("min_bedrooms", "bedrooms >= %(min_bedrooms)s"),
    ("max_bedrooms", "bedrooms <= %(max_bedrooms)s"),
    ("min_area_sqft", "area_sqft >= %(min_area_sqft)s"),
    ("move_in_from", "move_in_date >= %(move_in_from)s"),
    ("move_in_to", "move_in_date <= %(move_in_to)s"),
    ("amenities", "amenities @> %(amenities)s::text[]"),
    ("south", "latitude >= %(south)s"),
    ("north", "latitude <= %(north)s"),
    ("west", "longitude >= %(west)s"),
    ("east", "longitude <= %(east)s"),
]


@dataclass(frozen=True)
class SourceRecordView:
    """A source record with the source it came from, for listing cards."""

    id: UUID
    listing_id: UUID
    source_name: str
    source_kind: str
    is_synthetic: bool
    external_id: str
    original_url: str | None
    collected_at: dt.datetime


class ListingMapper(Mapper):
    def insert(self, values: dict[str, Any]) -> Listing:
        unknown = set(values) - _LISTING_WRITABLE
        if unknown:
            raise ValueError(f"not listing columns: {sorted(unknown)}")
        names = list(values)
        params = {k: jsonb(v) if k in _JSON_COLUMNS else v for k, v in values.items()}
        sql = f"""
            INSERT INTO listing ({", ".join(names)})
            VALUES ({", ".join(f"%({n})s" for n in names)})
            RETURNING {_LISTING}"""
        listing = self._one(Listing, sql, params)
        assert listing is not None
        return listing

    def find(self, listing_id: UUID) -> Listing | None:
        return self._one(Listing, f"SELECT {_LISTING} FROM listing WHERE id = %(id)s", {"id": listing_id})

    def lock(self, listing_id: UUID) -> Listing | None:
        return self._one(Listing, f"SELECT {_LISTING} FROM listing WHERE id = %(id)s FOR UPDATE", {"id": listing_id})

    def find_many(self, listing_ids: list[UUID]) -> list[Listing]:
        return self._all(Listing, f"SELECT {_LISTING} FROM listing WHERE id = ANY(%(ids)s)", {"ids": listing_ids})

    def set_status(self, listing_id: UUID, status: str, merged_into_id: UUID | None = None) -> int:
        return self._exec(
            "UPDATE listing SET status = %(status)s, merged_into_id = %(merged)s WHERE id = %(id)s",
            {"id": listing_id, "status": status, "merged": merged_into_id},
        )

    def find_same_unit(self, postal_code: str | None, address_line: str, unit: str | None) -> list[Listing]:
        """Candidates for the same apartment: same normalized address and unit. Never proof (R-2.3)."""
        sql = f"""
            SELECT {_LISTING} FROM listing
             WHERE status IN ('searchable', 'under_review')
               AND postal_code IS NOT DISTINCT FROM %(postal)s
               AND lower(address_line) = lower(%(address)s)
               AND lower(coalesce(unit, '')) = lower(coalesce(%(unit)s, ''))
             ORDER BY created_at"""
        return self._all(Listing, sql, {"postal": postal_code, "address": address_line, "unit": unit})

    def search(self, f: ListingFilter, sort: ListingSort, limit: int, offset: int) -> tuple[list[Listing], int]:
        clauses = ["status = 'searchable'"]
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        for name, clause in _CLAUSES:
            value = getattr(f, name)
            if value is not None and value != []:
                clauses.append(clause)
                params[name] = value
        if f.no_broker_fee:
            clauses.append("broker_fee_cents = 0")
        where = " AND ".join(clauses)
        total = int(self._scalar(f"SELECT count(*) FROM listing WHERE {where}", params))
        sql = f"SELECT {_LISTING} FROM listing WHERE {where} ORDER BY {_ORDER[sort]} LIMIT %(limit)s OFFSET %(offset)s"
        return self._all(Listing, sql, params), total


class SourceMapper(Mapper):
    def list_all(self) -> list[ListingSource]:
        return self._all(ListingSource, f"SELECT {_SOURCE} FROM listing_source ORDER BY name")

    def find(self, source_id: UUID) -> ListingSource | None:
        return self._one(ListingSource, f"SELECT {_SOURCE} FROM listing_source WHERE id = %(id)s", {"id": source_id})

    def find_by_name(self, name: str) -> ListingSource | None:
        return self._one(ListingSource, f"SELECT {_SOURCE} FROM listing_source WHERE name = %(name)s", {"name": name})

    def insert(self, name: str, kind: str, *, enabled: bool, is_synthetic: bool, config: dict[str, Any]) -> ListingSource:
        sql = f"""
            INSERT INTO listing_source (name, kind, enabled, is_synthetic, config)
            VALUES (%(name)s, %(kind)s, %(enabled)s, %(is_synthetic)s, %(config)s)
            RETURNING {_SOURCE}"""
        params = {"name": name, "kind": kind, "enabled": enabled, "is_synthetic": is_synthetic, "config": jsonb(config)}
        source = self._one(ListingSource, sql, params)
        assert source is not None
        return source

    def update(self, source_id: UUID, *, name: str | None, enabled: bool | None, config: dict[str, Any] | None) -> ListingSource | None:
        sql = f"""
            UPDATE listing_source
               SET name = coalesce(%(name)s, name),
                   enabled = coalesce(%(enabled)s, enabled),
                   config = coalesce(%(config)s, config)
             WHERE id = %(id)s
            RETURNING {_SOURCE}"""
        params = {"id": source_id, "name": name, "enabled": enabled, "config": None if config is None else jsonb(config)}
        return self._one(ListingSource, sql, params)


class SourceRecordMapper(Mapper):
    def insert(
        self,
        *,
        source_id: UUID,
        listing_id: UUID | None,
        external_id: str,
        original_url: str | None,
        collected_at: dt.datetime,
        raw_values: dict[str, Any],
        submitted_by: UUID | None,
    ) -> SourceRecord | None:
        """Insert one fetch. Returns None when the same fetch was already stored (a retry)."""
        sql = f"""
            INSERT INTO source_record (source_id, listing_id, external_id, original_url, collected_at, raw_values, submitted_by)
            VALUES (%(source_id)s, %(listing_id)s, %(external_id)s, %(original_url)s, %(collected_at)s, %(raw_values)s, %(submitted_by)s)
            ON CONFLICT ON CONSTRAINT source_record_fetch_key DO NOTHING
            RETURNING {_RECORD}"""
        params = {"source_id": source_id, "listing_id": listing_id, "external_id": external_id,
                  "original_url": original_url, "collected_at": collected_at, "raw_values": jsonb(raw_values),
                  "submitted_by": submitted_by}
        return self._one(SourceRecord, sql, params)

    def find(self, record_id: UUID) -> SourceRecord | None:
        return self._one(SourceRecord, f"SELECT {_RECORD} FROM source_record WHERE id = %(id)s", {"id": record_id})

    def latest_for_listing(self, listing_id: UUID) -> SourceRecord | None:
        sql = f"SELECT {_RECORD} FROM source_record WHERE listing_id = %(id)s ORDER BY collected_at DESC LIMIT 1"
        return self._one(SourceRecord, sql, {"id": listing_id})

    def views_for_card(self, listing_id: UUID) -> list[SourceRecordView]:
        """Every record behind a card, including those of listings merged into it (R-2.2, R-2.3)."""
        sql = """
            SELECT r.id, r.listing_id, s.name AS source_name, s.kind AS source_kind, s.is_synthetic,
                   r.external_id, r.original_url, r.collected_at
              FROM source_record r JOIN listing_source s ON s.id = r.source_id
             WHERE r.listing_id = %(id)s
                OR r.listing_id IN (SELECT id FROM listing WHERE merged_into_id = %(id)s)
             ORDER BY r.collected_at DESC"""
        return self._all(SourceRecordView, sql, {"id": listing_id})

    def clear_submitter(self, user_id: UUID) -> int:
        return self._exec("UPDATE source_record SET submitted_by = NULL WHERE submitted_by = %(id)s", {"id": user_id})


class PriceHistoryMapper(Mapper):
    def insert(self, listing_id: UUID, source_record_id: UUID | None, rent_cents: int, observed_at: dt.datetime) -> None:
        self._exec(
            """INSERT INTO listing_price_history (listing_id, source_record_id, rent_cents, observed_at)
               VALUES (%(listing_id)s, %(record)s, %(rent)s, %(at)s)""",
            {"listing_id": listing_id, "record": source_record_id, "rent": rent_cents, "at": observed_at},
        )

    def list_for_listing(self, listing_id: UUID) -> list[PricePoint]:
        sql = f"SELECT {columns(PricePoint)} FROM listing_price_history WHERE listing_id = %(id)s ORDER BY observed_at"
        return self._all(PricePoint, sql, {"id": listing_id})


class DuplicateMapper(Mapper):
    def insert(self, record_a_id: UUID, record_b_id: UUID, confidence: float) -> DuplicateCandidate:
        sql = f"""
            INSERT INTO duplicate_candidate (record_a_id, record_b_id, confidence)
            VALUES (%(a)s, %(b)s, %(confidence)s)
            RETURNING {_CANDIDATE}"""
        candidate = self._one(DuplicateCandidate, sql, {"a": record_a_id, "b": record_b_id, "confidence": confidence})
        assert candidate is not None
        return candidate

    def lock(self, candidate_id: UUID) -> DuplicateCandidate | None:
        sql = f"SELECT {_CANDIDATE} FROM duplicate_candidate WHERE id = %(id)s FOR UPDATE"
        return self._one(DuplicateCandidate, sql, {"id": candidate_id})

    def find(self, candidate_id: UUID) -> DuplicateCandidate | None:
        return self._one(DuplicateCandidate, f"SELECT {_CANDIDATE} FROM duplicate_candidate WHERE id = %(id)s", {"id": candidate_id})

    def list_by_status(self, status: str, limit: int, offset: int) -> tuple[list[DuplicateCandidate], int]:
        params = {"status": status, "limit": limit, "offset": offset}
        total = int(self._scalar("SELECT count(*) FROM duplicate_candidate WHERE status = %(status)s", params))
        sql = f"""
            SELECT {_CANDIDATE} FROM duplicate_candidate WHERE status = %(status)s
             ORDER BY created_at LIMIT %(limit)s OFFSET %(offset)s"""
        return self._all(DuplicateCandidate, sql, params), total

    def set_status(self, candidate_id: UUID, status: str, reviewed_by: UUID) -> DuplicateCandidate:
        sql = f"""
            UPDATE duplicate_candidate SET status = %(status)s, reviewed_by = %(by)s, reviewed_at = now()
             WHERE id = %(id)s
            RETURNING {_CANDIDATE}"""
        candidate = self._one(DuplicateCandidate, sql, {"id": candidate_id, "status": status, "by": reviewed_by})
        assert candidate is not None
        return candidate

    def count_queued_for_listing(self, listing_id: UUID) -> int:
        return int(self._scalar(
            """SELECT count(*) FROM duplicate_candidate c JOIN source_record r ON r.id IN (c.record_a_id, c.record_b_id)
                WHERE c.status = 'queued' AND r.listing_id = %(id)s""",
            {"id": listing_id},
        ))


class ReportMapper(Mapper):
    def insert(self, listing_id: UUID, reporter_id: UUID, reason: str, details: str | None) -> DataReport:
        sql = f"""
            INSERT INTO data_report (listing_id, reporter_id, reason, details)
            VALUES (%(listing)s, %(reporter)s, %(reason)s, %(details)s)
            RETURNING {_REPORT}"""
        params = {"listing": listing_id, "reporter": reporter_id, "reason": reason, "details": details}
        report = self._one(DataReport, sql, params)
        assert report is not None
        return report

    def list_by_status(self, status: str, limit: int, offset: int) -> tuple[list[DataReport], int]:
        params = {"status": status, "limit": limit, "offset": offset}
        total = int(self._scalar("SELECT count(*) FROM data_report WHERE status = %(status)s", params))
        sql = f"""
            SELECT {_REPORT} FROM data_report WHERE status = %(status)s
             ORDER BY created_at LIMIT %(limit)s OFFSET %(offset)s"""
        return self._all(DataReport, sql, params), total

    def resolve(self, report_id: UUID, status: str, resolved_by: UUID) -> DataReport | None:
        sql = f"""
            UPDATE data_report SET status = %(status)s, resolved_by = %(by)s, resolved_at = now()
             WHERE id = %(id)s AND status = 'open'
            RETURNING {_REPORT}"""
        return self._one(DataReport, sql, {"id": report_id, "status": status, "by": resolved_by})
