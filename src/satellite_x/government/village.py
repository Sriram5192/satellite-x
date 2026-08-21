from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from datetime import datetime

from ..models import utc_now
from .models import FieldGovernmentRecord, VillageSummary


class VillageAggregator:
    def __init__(
        self,
        clock: Callable[[], datetime] = utc_now,
        *,
        minimum_group_size: int = 5,
    ):
        if minimum_group_size < 5:
            raise ValueError("government aggregate minimum_group_size cannot be below 5")
        self.clock = clock
        self.minimum_group_size = minimum_group_size

    def aggregate(self, village_code: str, fields: list[FieldGovernmentRecord]) -> VillageSummary:
        selected = [item for item in fields if item.village_code == village_code]
        if len(selected) < self.minimum_group_size:
            return VillageSummary(
                village_code=village_code,
                generated_at=self.clock(),
                privacy_status="suppressed_small_group",
                minimum_group_size=self.minimum_group_size,
                suppression_reason=(
                    f"Aggregate suppressed because fewer than {self.minimum_group_size} fields are in scope."
                ),
                contains_personal_data=False,
            )
        crop = defaultdict(float)
        verdict = defaultdict(float)
        for item in selected:
            crop[item.crop_type] += item.area_acres
            verdict[item.verdict] += item.area_acres
        return VillageSummary(
            village_code=village_code,
            generated_at=self.clock(),
            privacy_status="released",
            minimum_group_size=self.minimum_group_size,
            field_count=len(selected),
            total_agri_acres=round(sum(item.area_acres for item in selected), 3),
            crop_acres={key: round(value, 3) for key, value in sorted(crop.items())},
            verdict_acres={key: round(value, 3) for key, value in sorted(verdict.items())},
            verification_required_fields=sum(item.ground_verification_required for item in selected),
            low_confidence_fields=sum(item.confidence_pct < 50 for item in selected),
            contains_personal_data=False,
        )
