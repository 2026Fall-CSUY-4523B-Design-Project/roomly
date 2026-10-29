"""SQL for commute_destination and saved_search. Listing search itself is ListingMapper.search."""

from typing import Any
from uuid import UUID

from roomly.entity import CommuteDestination, SavedSearch
from roomly.mapper.base import Mapper, columns, jsonb

_DESTINATION = columns(CommuteDestination)
_SAVED = columns(SavedSearch)


class CommuteMapper(Mapper):
    def list_for_user(self, user_id: UUID) -> list[CommuteDestination]:
        sql = f"SELECT {_DESTINATION} FROM commute_destination WHERE user_id = %(id)s ORDER BY created_at"
        return self._all(CommuteDestination, sql, {"id": user_id})

    def count_for_user(self, user_id: UUID) -> int:
        return int(self._scalar("SELECT count(*) FROM commute_destination WHERE user_id = %(id)s", {"id": user_id}))

    def insert(
        self, user_id: UUID, label: str, address: str | None, latitude: float | None, longitude: float | None, mode: str
    ) -> CommuteDestination:
        sql = f"""
            INSERT INTO commute_destination (user_id, label, address, latitude, longitude, mode)
            VALUES (%(user_id)s, %(label)s, %(address)s, %(lat)s, %(lng)s, %(mode)s)
            RETURNING {_DESTINATION}"""
        params = {"user_id": user_id, "label": label, "address": address, "lat": latitude, "lng": longitude, "mode": mode}
        destination = self._one(CommuteDestination, sql, params)
        assert destination is not None
        return destination

    def delete(self, destination_id: UUID, user_id: UUID) -> int:
        return self._exec(
            "DELETE FROM commute_destination WHERE id = %(id)s AND user_id = %(user_id)s",
            {"id": destination_id, "user_id": user_id},
        )

    def delete_all_for_user(self, user_id: UUID) -> int:
        return self._exec("DELETE FROM commute_destination WHERE user_id = %(id)s", {"id": user_id})


class SavedSearchMapper(Mapper):
    def list_for_user(self, user_id: UUID) -> list[SavedSearch]:
        sql = f"SELECT {_SAVED} FROM saved_search WHERE user_id = %(id)s ORDER BY created_at DESC"
        return self._all(SavedSearch, sql, {"id": user_id})

    def find_for_user(self, search_id: UUID, user_id: UUID) -> SavedSearch | None:
        sql = f"SELECT {_SAVED} FROM saved_search WHERE id = %(id)s AND user_id = %(user_id)s"
        return self._one(SavedSearch, sql, {"id": search_id, "user_id": user_id})

    def insert(
        self, user_id: UUID, name: str, criteria: dict[str, Any], weights: dict[str, Any], alerts_enabled: bool
    ) -> SavedSearch:
        sql = f"""
            INSERT INTO saved_search (user_id, name, criteria, weights, alerts_enabled)
            VALUES (%(user_id)s, %(name)s, %(criteria)s, %(weights)s, %(alerts)s)
            RETURNING {_SAVED}"""
        params = {"user_id": user_id, "name": name, "criteria": jsonb(criteria), "weights": jsonb(weights),
                  "alerts": alerts_enabled}
        saved = self._one(SavedSearch, sql, params)
        assert saved is not None
        return saved

    def delete(self, search_id: UUID, user_id: UUID) -> int:
        return self._exec("DELETE FROM saved_search WHERE id = %(id)s AND user_id = %(user_id)s",
                          {"id": search_id, "user_id": user_id})

    def delete_all_for_user(self, user_id: UUID) -> int:
        return self._exec("DELETE FROM saved_search WHERE user_id = %(id)s", {"id": user_id})
