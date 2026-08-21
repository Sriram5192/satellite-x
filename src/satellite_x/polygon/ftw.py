"""Cloud-native Fields of The World GeoParquet query client."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ..config import Settings
from .errors import FtwQueryError
from .math_utils import ACRE_M2, search_bbox
from .models import PolygonRecoveryInput


@dataclass(frozen=True, slots=True)
class RawFtwRecord:
    record_id: str
    observed_at: datetime
    year: int
    confidence: float | None
    area_m2: float
    perimeter_m: float
    geometry_geojson: dict[str, Any]


class FtwRepository:
    def __init__(self, settings: Settings):
        self.settings = settings

    def query(self, request: PolygonRecoveryInput) -> list[RawFtwRecord]:
        try:
            import duckdb
        except ImportError as exc:
            raise FtwQueryError(
                "duckdb is required; install project dependencies"
            ) from exc

        subdivision = request.subdivision_code
        if not subdivision:
            raise FtwQueryError("subdivision_code is required for FTW partition query")
        country = request.country_code
        partition = f"{country}_{subdivision}.parquet"
        url = (
            f"{self.settings.ftw_vectors_base_url}/"
            f"admin:country_code={country}/{partition}"
        )
        xmin, ymin, xmax, ymax = search_bbox(
            request.latitude, request.longitude, request.search_radius_m
        )
        target_m2 = request.acres * ACRE_M2
        minimum_area = target_m2 * self.settings.ftw_min_area_ratio
        maximum_area = target_m2 * self.settings.ftw_max_area_ratio
        limit = self.settings.ftw_query_limit

        query = f'''
            SELECT
                id,
                "determination:datetime" AS observed_at,
                EXTRACT(year FROM "determination:datetime")::INTEGER AS year,
                confidence,
                "metrics:area" AS area_m2,
                "metrics:perimeter" AS perimeter_m,
                ST_AsGeoJSON(geometry) AS geometry_json
            FROM read_parquet('{url}')
            WHERE bbox.xmax >= {float(xmin)}
              AND bbox.xmin <= {float(xmax)}
              AND bbox.ymax >= {float(ymin)}
              AND bbox.ymin <= {float(ymax)}
              AND "determination:datetime" >= TIMESTAMPTZ '2024-01-01'
              AND "determination:datetime" < TIMESTAMPTZ '2026-01-01'
              AND "metrics:area" BETWEEN {float(minimum_area)} AND {float(maximum_area)}
            ORDER BY observed_at DESC,
                     abs("metrics:area" - {float(target_m2)}) ASC
            LIMIT {int(limit)}
        '''
        connection = duckdb.connect(database=":memory:")
        try:
            self._load_extension(connection, "httpfs")
            self._load_extension(connection, "spatial")
            rows = connection.execute(query).fetchall()
        except Exception as exc:
            raise FtwQueryError(
                f"FTW query failed for {country}-{subdivision}: {exc}"
            ) from exc
        finally:
            connection.close()

        records: list[RawFtwRecord] = []
        for row in rows:
            try:
                geometry = json.loads(row[6])
                records.append(
                    RawFtwRecord(
                        record_id=str(row[0]),
                        observed_at=row[1],
                        year=int(row[2]),
                        confidence=float(row[3]) if row[3] is not None else None,
                        area_m2=float(row[4]),
                        perimeter_m=float(row[5]),
                        geometry_geojson=geometry,
                    )
                )
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                raise FtwQueryError(f"invalid FTW record: {exc}") from exc
        return records

    @staticmethod
    def _load_extension(connection: Any, name: str) -> None:
        try:
            connection.execute(f"LOAD {name}")
        except Exception:
            connection.execute(f"INSTALL {name}")
            connection.execute(f"LOAD {name}")
