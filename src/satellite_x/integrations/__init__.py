"""Authorization-gated external service adapters."""

from .government import (
    GovernmentConnectorConfig,
    GovernmentConnectorResult,
    GovernmentFetchInput,
    GovernmentRecordGateway,
)
from .otp import OtpService, SmsTransport

__all__ = [
    "GovernmentConnectorConfig", "GovernmentConnectorResult", "GovernmentFetchInput", "GovernmentRecordGateway",
    "OtpService", "SmsTransport",
]
