"""ComparisonService (§9.1 control class): side-by-side comparison of 2-4 listings (R-4).

Best-value highlighting only ever looks at known values (an Unknown is never "best"), needs
at least two of them, and states its direction. Saved comparisons keep a snapshot of each
listing so later changes are reported instead of silently replacing what was compared.
"""

from uuid import UUID

from roomly.db import Database
from roomly.dto.comparison import (
    ComparisonDTO,
    ComparisonSummaryDTO,
    ComparisonTableDTO,
    PreviewRequest,
    SaveComparisonRequest,
    ShareRequest,
)
from roomly.entity import User


class ComparisonService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def preview(self, req: PreviewRequest) -> ComparisonTableDTO:
        raise NotImplementedError

    def save(self, user: User, req: SaveComparisonRequest) -> ComparisonDTO:
        raise NotImplementedError

    def get(self, user: User, comparison_id: UUID) -> ComparisonDTO:
        raise NotImplementedError

    def share(self, user: User, comparison_id: UUID, req: ShareRequest) -> ComparisonDTO:
        raise NotImplementedError

    def list_for_group(self, user: User, group_id: UUID) -> list[ComparisonSummaryDTO]:
        raise NotImplementedError

    def list_personal(self, user: User) -> list[ComparisonSummaryDTO]:
        raise NotImplementedError
