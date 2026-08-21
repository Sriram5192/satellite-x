"""Resilient JSON HTTP transport with bounded retries and timeouts."""

from __future__ import annotations

from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import Settings
from .errors import ExternalServiceError


class JsonHttpClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.session = requests.Session()
        retry = Retry(
            total=settings.retries,
            connect=settings.retries,
            read=settings.retries,
            status=settings.retries,
            backoff_factor=settings.backoff_factor,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET", "POST"}),
            respect_retry_after_header=True,
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.session.headers.update(
            {"Accept": "application/json", "User-Agent": settings.user_agent}
        )

    @property
    def timeout(self) -> tuple[float, float]:
        return (self.settings.connect_timeout_s, self.settings.read_timeout_s)

    def get_json(
        self, service: str, url: str, *, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return self._request_json(service, "GET", url, params=params)

    def post_json(
        self, service: str, url: str, *, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return self._request_json(service, "POST", url, json=payload)

    def _request_json(self, service: str, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = self.session.request(method, url, timeout=self.timeout, **kwargs)
        except requests.RequestException as exc:
            raise ExternalServiceError(service, f"request failed: {exc}") from exc
        if not response.ok:
            excerpt = response.text[:300].replace("\n", " ")
            raise ExternalServiceError(
                service, f"HTTP {response.status_code}; response={excerpt!r}"
            )
        try:
            payload = response.json()
        except requests.JSONDecodeError as exc:
            raise ExternalServiceError(service, "response is not valid JSON") from exc
        if not isinstance(payload, dict):
            raise ExternalServiceError(service, "top-level JSON must be an object")
        if payload.get("error") is True:
            raise ExternalServiceError(service, str(payload.get("reason", "API error")))
        return payload

    def close(self) -> None:
        self.session.close()

    def __enter__(self) -> "JsonHttpClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
