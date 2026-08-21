from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from ..models import StrictModel


class AtmosphericLossInput(StrictModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    frequency_ghz: float = Field(gt=0, le=55)
    elevation_deg: float = Field(gt=0, le=90)
    exceedance_probability_pct: float = Field(ge=0.001, le=50)
    antenna_diameter_m: float = Field(gt=0)
    station_altitude_km: float | None = None
    water_vapour_density_g_m3: float | None = Field(default=None, gt=0)
    rainfall_rate_001_mm_h: float | None = Field(default=None, ge=0)
    temperature_k: float | None = Field(default=None, gt=0)
    pressure_hpa: float | None = Field(default=None, gt=0)
    measured_ionospheric_fade_db: float | None = Field(default=None, ge=0)


class AtmosphericLossResult(StrictModel):
    model: Literal["ITU-R_P.618_with_P.676_P.837_P.840"]
    gaseous_db: float
    cloud_db: float
    rain_db: float
    tropospheric_scintillation_db: float
    modeled_total_db: float
    ionospheric_fade_db: float | None
    combined_total_db: float
    ionospheric_status: Literal[
        "measured_value_included",
        "not_applied_x_band_above_6_ghz",
        "requires_measured_or_calibrated_input",
    ]
    live_beacon_calibrated: Literal[False] = False
    warnings: list[str]


class LinkBudgetInput(StrictModel):
    calibration_status: Literal["caller_supplied_validation_fixture", "measured_operational_inputs"]
    frequency_ghz: float = Field(gt=0)
    range_km: float = Field(gt=0)
    data_rate_bps: float = Field(gt=0)
    transmit_eirp_dbw: float
    receive_antenna_diameter_m: float = Field(gt=0)
    receive_antenna_efficiency: float = Field(gt=0, le=1)
    system_noise_temperature_k: float = Field(gt=0)
    atmospheric_loss_db: float = Field(ge=0)
    other_losses_db: float = Field(default=0, ge=0)
    required_eb_n0_db: float
    range_rate_km_s: float = 0


class LinkBudgetResult(StrictModel):
    calibration_status: str
    free_space_path_loss_db: float
    receive_antenna_gain_dbi: float
    received_carrier_power_dbw: float
    noise_density_dbw_hz: float
    c_n0_db_hz: float
    eb_n0_db: float
    link_margin_db: float
    doppler_shift_hz: float
    status: Literal["margin_positive", "margin_negative"]
    assumptions: list[str]


class ContactWindow(StrictModel):
    window_id: str
    start_second: int = Field(ge=0)
    end_second: int = Field(gt=0)
    channel_count: int = Field(ge=1)
    per_channel_capacity_mbps: float = Field(gt=0)

    @model_validator(mode="after")
    def order(self) -> "ContactWindow":
        if self.end_second <= self.start_second:
            raise ValueError("contact end_second must be after start_second")
        return self


class TrafficRequest(StrictModel):
    request_id: str
    station_id: str
    arrival_second: int = Field(ge=0)
    deadline_second: int = Field(gt=0)
    data_megabits: float = Field(gt=0)
    priority: int = Field(default=1, ge=1, le=10)

    @model_validator(mode="after")
    def deadline_after_arrival(self) -> "TrafficRequest":
        if self.deadline_second <= self.arrival_second:
            raise ValueError("request deadline must be after arrival")
        return self


class TrafficSimulationInput(StrictModel):
    scenario_purpose: Literal["deterministic_validation_fixture", "authorized_mission_trace"]
    simulation_duration_seconds: int = Field(gt=0, le=86400)
    time_step_seconds: int = Field(default=1, ge=1, le=60)
    contacts: list[ContactWindow] = Field(min_length=1)
    requests: list[TrafficRequest] = Field(min_length=1)
    scheduling_policy: Literal["priority_earliest_deadline"] = "priority_earliest_deadline"


class RequestOutcome(StrictModel):
    request_id: str
    station_id: str
    status: Literal["completed", "dropped_deadline", "dropped_simulation_end"]
    requested_megabits: float
    transmitted_megabits: float
    dropped_megabits: float
    first_service_second: int | None
    completion_second: int | None
    queue_wait_seconds: int | None


class TrafficSimulationResult(StrictModel):
    scenario_purpose: str
    scheduling_policy: str
    total_requests: int
    completed_requests: int
    dropped_requests: int
    packet_drop_request_pct: float
    requested_megabits: float
    transmitted_megabits: float
    dropped_megabits: float
    throughput_mbps: float
    available_capacity_megabits: float
    channel_utilization_pct: float
    mean_completed_queue_wait_seconds: float | None
    outcomes: list[RequestOutcome]
    warnings: list[str]
