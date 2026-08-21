"""Polygon engine errors."""


class PolygonRecoveryError(Exception):
    pass


class LocationPreflightError(PolygonRecoveryError):
    pass


class FtwQueryError(PolygonRecoveryError):
    pass


class BoundaryValidationError(PolygonRecoveryError):
    pass
