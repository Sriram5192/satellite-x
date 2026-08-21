"""Domain-specific failures for the Set 1 acquisition layer."""


class SatelliteXError(Exception):
    """Base error for SATELLITE-X."""


class ExternalServiceError(SatelliteXError):
    """An external service failed or returned an invalid payload."""

    def __init__(self, service: str, message: str):
        super().__init__(f"{service}: {message}")
        self.service = service
        self.message = message


class NoSatelliteSceneError(SatelliteXError):
    """No Sentinel-2 scene with all required assets could be acquired."""


class CacheMissError(SatelliteXError):
    """No usable cached response exists for a failed live request."""
