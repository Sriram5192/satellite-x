from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest


FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def load_fixture():
    def load(name: str) -> dict[str, Any]:
        return json.loads((FIXTURES / name).read_text(encoding="utf-8"))

    return load


class RouteHttp:
    def __init__(self, *, stac=None, weather=None, soil=None, failure: Exception | None = None):
        self.stac = stac
        self.weather = weather
        self.soil = soil
        self.failure = failure
        self.calls: list[tuple[str, str]] = []

    def post_json(self, service, url, *, payload):
        self.calls.append((service, url))
        if self.failure:
            raise self.failure
        if self.stac is None:
            raise AssertionError(f"unexpected POST {service}")
        return self.stac

    def get_json(self, service, url, *, params=None):
        self.calls.append((service, url))
        if self.failure:
            raise self.failure
        if service.startswith("open_meteo"):
            if self.weather is None:
                raise AssertionError(f"unexpected weather GET {url}")
            return self.weather
        if service == "soilgrids":
            if self.soil is None:
                raise AssertionError(f"unexpected soil GET {url}")
            return self.soil
        raise AssertionError(f"unexpected GET {service}")

    def close(self):
        pass
