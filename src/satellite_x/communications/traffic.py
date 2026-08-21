"""Deterministic scheduled-contact discrete-event/time-step resource allocator."""
from __future__ import annotations

from statistics import fmean

from .models import (
    RequestOutcome, TrafficSimulationInput, TrafficSimulationResult,
)


class DynamicContactScheduler:
    def run(self, request: TrafficSimulationInput) -> TrafficSimulationResult:
        jobs = {
            item.request_id: {
                "request": item,
                "remaining": float(item.data_megabits),
                "transmitted": 0.0,
                "first": None,
                "completion": None,
                "status": None,
            }
            for item in request.requests
        }
        if len(jobs) != len(request.requests):
            raise ValueError("request_id values must be unique")
        pending = []
        arrived: set[str] = set()
        available_capacity = 0.0
        step = request.time_step_seconds
        for current in range(0, request.simulation_duration_seconds, step):
            interval = min(step, request.simulation_duration_seconds - current)
            for item in request.requests:
                if item.request_id not in arrived and item.arrival_second <= current:
                    pending.append(item.request_id)
                    arrived.add(item.request_id)
            still_pending = []
            for request_id in pending:
                job = jobs[request_id]
                if job["request"].deadline_second <= current:
                    job["status"] = "dropped_deadline"
                else:
                    still_pending.append(request_id)
            pending = still_pending
            channels = []
            for contact in request.contacts:
                if contact.start_second <= current and contact.end_second >= current + interval:
                    channels.extend(
                        [contact.per_channel_capacity_mbps] * contact.channel_count
                    )
            available_capacity += sum(channels) * interval
            pending.sort(
                key=lambda request_id: (
                    -jobs[request_id]["request"].priority,
                    jobs[request_id]["request"].deadline_second,
                    jobs[request_id]["request"].arrival_second,
                    request_id,
                )
            )
            selected = pending[: len(channels)]
            completed_this_step = []
            for request_id, capacity_mbps in zip(selected, channels):
                job = jobs[request_id]
                if job["first"] is None:
                    job["first"] = current
                amount = min(job["remaining"], capacity_mbps * interval)
                job["remaining"] -= amount
                job["transmitted"] += amount
                if job["remaining"] <= 1e-9:
                    job["remaining"] = 0.0
                    job["completion"] = current + interval
                    job["status"] = "completed"
                    completed_this_step.append(request_id)
            if completed_this_step:
                complete = set(completed_this_step)
                pending = [item for item in pending if item not in complete]
        for request_id in pending:
            job = jobs[request_id]
            job["status"] = (
                "dropped_deadline"
                if job["request"].deadline_second <= request.simulation_duration_seconds
                else "dropped_simulation_end"
            )
        outcomes = []
        for item in request.requests:
            job = jobs[item.request_id]
            status = job["status"] or "dropped_simulation_end"
            outcomes.append(
                RequestOutcome(
                    request_id=item.request_id,
                    station_id=item.station_id,
                    status=status,
                    requested_megabits=round(item.data_megabits, 6),
                    transmitted_megabits=round(job["transmitted"], 6),
                    dropped_megabits=round(item.data_megabits - job["transmitted"], 6),
                    first_service_second=job["first"],
                    completion_second=job["completion"],
                    queue_wait_seconds=(
                        job["first"] - item.arrival_second
                        if job["first"] is not None else None
                    ),
                )
            )
        completed = [item for item in outcomes if item.status == "completed"]
        requested_total = sum(item.requested_megabits for item in outcomes)
        transmitted_total = sum(item.transmitted_megabits for item in outcomes)
        dropped_total = sum(item.dropped_megabits for item in outcomes)
        return TrafficSimulationResult(
            scenario_purpose=request.scenario_purpose,
            scheduling_policy=request.scheduling_policy,
            total_requests=len(outcomes),
            completed_requests=len(completed),
            dropped_requests=len(outcomes) - len(completed),
            packet_drop_request_pct=round(
                100 * (len(outcomes) - len(completed)) / len(outcomes), 6
            ),
            requested_megabits=round(requested_total, 6),
            transmitted_megabits=round(transmitted_total, 6),
            dropped_megabits=round(dropped_total, 6),
            throughput_mbps=round(
                transmitted_total / request.simulation_duration_seconds, 6
            ),
            available_capacity_megabits=round(available_capacity, 6),
            channel_utilization_pct=round(
                100 * transmitted_total / available_capacity
                if available_capacity else 0.0,
                6,
            ),
            mean_completed_queue_wait_seconds=(
                round(fmean(item.queue_wait_seconds for item in completed), 6)
                if completed else None
            ),
            outcomes=outcomes,
            warnings=[
                "This scheduled-contact DES is a resource-contention model, not a claim about the operational Sentinel ground segment.",
                "Traffic inputs and contact capacity must be replaced with authorized mission traces for operational conclusions.",
            ],
        )
