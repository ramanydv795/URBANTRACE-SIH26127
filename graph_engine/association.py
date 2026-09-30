"""
URBANTRACE Part 3 - Cross-Camera Association Engine

Greedy, chronological, explainable association.

Thresholds:
    >= 0.85  -> auto_linked
    >= 0.55  -> pending_review
    <  0.55  -> new vehicle

This is intentionally a batch worker rather than a live service.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .fusion import FusionResult, compute_fusion
from .repository import GraphRepository


AUTO_LINK_THRESHOLD = 0.85
REVIEW_THRESHOLD = 0.55


@dataclass
class OpenVehicle:
    vehicle_id: str
    observation: dict[str, Any]
    reid_vector: list[float] | None


class AssociationEngine:
    def __init__(
        self,
        repository: GraphRepository | None = None,
    ):
        self.repository = repository or GraphRepository()

        # vehicle_id -> most recent observation state
        self.open_vehicles: dict[str, OpenVehicle] = {}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _topology_min(edge: dict[str, Any]) -> float | None:
        """
        Support the expected topology naming.
        """

        for key in (
            "min_travel_s",
            "min_travel_seconds",
            "travel_min_s",
        ):
            if key in edge and edge[key] is not None:
                return float(edge[key])

        return None

    @staticmethod
    def _topology_max(edge: dict[str, Any]) -> float | None:
        """
        Support the expected topology naming.
        """

        for key in (
            "max_travel_s",
            "max_travel_seconds",
            "travel_max_s",
        ):
            if key in edge and edge[key] is not None:
                return float(edge[key])

        return None

    # ------------------------------------------------------------------
    # Candidate search
    # ------------------------------------------------------------------

    def _candidate_vehicles(
        self,
        observation: dict[str, Any],
    ) -> list[tuple[OpenVehicle, dict[str, Any]]]:
        """
        Find open vehicles whose previous camera has a topology edge
        reaching the current camera.
        """

        current_camera = observation["camera_code"]
        current_ts = observation["ts"]

        candidates = []

        for open_vehicle in self.open_vehicles.values():

            previous = open_vehicle.observation
            previous_camera = previous["camera_code"]
            previous_ts = previous["ts"]

            # Same-camera continuation is not a Part 3 cross-camera
            # transition.
            if previous_camera == current_camera:
                continue

            edge = self.repository.get_topology_edge(
                previous_camera,
                current_camera,
            )

            if edge is None:
                continue

            min_travel = self._topology_min(edge)
            max_travel = self._topology_max(edge)

            delta = (
                current_ts - previous_ts
            ).total_seconds()

            # Reject impossible temporal direction.
            if delta < 0:
                continue

            # If topology gives a maximum travel time, use it as a
            # hard candidate filter.
            if max_travel is not None and delta > max_travel:
                continue

            # If topology gives a minimum travel time, don't allow an
            # impossible instant transition.
            if min_travel is not None and delta < min_travel:
                continue

            candidates.append(
                (
                    open_vehicle,
                    edge,
                )
            )

        return candidates

    # ------------------------------------------------------------------
    # Score candidate
    # ------------------------------------------------------------------

    def _score_candidate(
        self,
        open_vehicle: OpenVehicle,
        edge: dict[str, Any],
        arrival: dict[str, Any],
    ) -> FusionResult:

        departure = open_vehicle.observation

        arrival_vector = self.repository.get_reid_vector(
            str(arrival["id"])
        )

        topology_min = self._topology_min(edge)
        topology_max = self._topology_max(edge)

        return compute_fusion(
            departure,
            arrival,
            reid_vector_departure=open_vehicle.reid_vector,
            reid_vector_arrival=arrival_vector,
            min_travel_s=topology_min,
            max_travel_s=topology_max,
            topology_exists=True,
        )

    # ------------------------------------------------------------------
    # Create new vehicle
    # ------------------------------------------------------------------

    def _start_new_vehicle(
        self,
        observation: dict[str, Any],
    ) -> OpenVehicle:

        # GraphRepository.create_vehicle() expects the observation.
        vehicle_id = self.repository.create_vehicle(
            observation
        )

        self.repository.assign_vehicle(
            str(observation["id"]),
            vehicle_id,
        )

        # This is a newly created vehicle, so its first_seen was already
        # populated by create_vehicle(). Only update last_seen here.
        self.repository.update_vehicle_times(
            vehicle_id,
            last_seen=observation["ts"],
        )

        reid_vector = self.repository.get_reid_vector(
            str(observation["id"])
        )

        open_vehicle = OpenVehicle(
            vehicle_id=vehicle_id,
            observation=observation,
            reid_vector=reid_vector,
        )

        self.open_vehicles[vehicle_id] = open_vehicle

        return open_vehicle

    # ------------------------------------------------------------------
    # Link vehicle
    # ------------------------------------------------------------------

    def _auto_link(
        self,
        open_vehicle: OpenVehicle,
        arrival: dict[str, Any],
        fusion: FusionResult,
    ) -> str:

        vehicle_id = open_vehicle.vehicle_id

        self.repository.assign_vehicle(
            str(arrival["id"]),
            vehicle_id,
        )

        # Update only last_seen because this is an existing vehicle.
        self.repository.update_vehicle_times(
            vehicle_id,
            last_seen=arrival["ts"],
        )

        # Pass the complete FusionResult so repository.py can persist
        # score, signals, timing, topology, plate similarity, Re-ID,
        # evidence, etc.
        transition_id = self.repository.create_transition(
            from_observation_id=str(
                open_vehicle.observation["id"]
            ),
            to_observation_id=str(arrival["id"]),
            vehicle_id=vehicle_id,
            fusion_result=fusion,
            status="auto_linked",
        )

        # Update open state only after successful linking.
        arrival_vector = self.repository.get_reid_vector(
            str(arrival["id"])
        )

        self.open_vehicles[vehicle_id] = OpenVehicle(
            vehicle_id=vehicle_id,
            observation=arrival,
            reid_vector=arrival_vector,
        )

        return transition_id

    # ------------------------------------------------------------------
    # Pending review
    # ------------------------------------------------------------------

    def _pending_review(
        self,
        open_vehicle: OpenVehicle,
        arrival: dict[str, Any],
        fusion: FusionResult,
    ) -> str:

        transition_id = self.repository.create_transition(
            from_observation_id=str(
                open_vehicle.observation["id"]
            ),
            to_observation_id=str(arrival["id"]),
            vehicle_id=None,
            fusion_result=fusion,
            status="pending_review",
        )

        self.repository.create_review_queue_item(
            transition_id
        )

        return transition_id

    # ------------------------------------------------------------------
    # Main observation processing
    # ------------------------------------------------------------------

    def process_observation(
        self,
        observation: dict[str, Any],
    ) -> dict[str, Any]:

        candidates = self._candidate_vehicles(
            observation
        )

        # ----------------------------------------------------------
        # No valid previous vehicle.
        # ----------------------------------------------------------

        if not candidates:

            vehicle = self._start_new_vehicle(
                observation
            )

            return {
                "observation_id": str(observation["id"]),
                "vehicle_id": vehicle.vehicle_id,
                "status": "new_vehicle",
                "score": None,
            }

        # ----------------------------------------------------------
        # Score every valid candidate.
        # ----------------------------------------------------------

        scored_candidates = []

        for open_vehicle, edge in candidates:

            fusion = self._score_candidate(
                open_vehicle,
                edge,
                observation,
            )

            scored_candidates.append(
                (
                    fusion.score,
                    open_vehicle,
                    fusion,
                )
            )

        # Highest score wins.
        scored_candidates.sort(
            key=lambda item: item[0],
            reverse=True,
        )

        best_score, best_vehicle, best_fusion = (
            scored_candidates[0]
        )

        # ----------------------------------------------------------
        # AUTO LINK
        # ----------------------------------------------------------

        if best_score >= AUTO_LINK_THRESHOLD:

            transition_id = self._auto_link(
                best_vehicle,
                observation,
                best_fusion,
            )

            return {
                "observation_id": str(observation["id"]),
                "vehicle_id": best_vehicle.vehicle_id,
                "status": "auto_linked",
                "score": best_score,
                "transition_id": transition_id,
                "evidence": best_fusion.evidence,
            }

        # ----------------------------------------------------------
        # REVIEW
        # ----------------------------------------------------------

        if best_score >= REVIEW_THRESHOLD:

            transition_id = self._pending_review(
                best_vehicle,
                observation,
                best_fusion,
            )

            # IMPORTANT:
            # Do not assign vehicle_id and do not extend open state.
            return {
                "observation_id": str(observation["id"]),
                "vehicle_id": None,
                "status": "pending_review",
                "score": best_score,
                "transition_id": transition_id,
                "evidence": best_fusion.evidence,
            }

        # ----------------------------------------------------------
        # No sufficiently good candidate.
        # ----------------------------------------------------------

        vehicle = self._start_new_vehicle(
            observation
        )

        return {
            "observation_id": str(observation["id"]),
            "vehicle_id": vehicle.vehicle_id,
            "status": "new_vehicle",
            "score": best_score,
            "evidence": best_fusion.evidence,
        }

    # ------------------------------------------------------------------
    # Batch execution
    # ------------------------------------------------------------------

    def run(self) -> list[dict[str, Any]]:

        observations = (
            self.repository.get_unresolved_observations()
        )

        results = []

        for observation in observations:

            result = self.process_observation(
                observation
            )

            results.append(result)

        return results


def run_association(
    repository: GraphRepository | None = None,
) -> list[dict[str, Any]]:

    engine = AssociationEngine(repository)

    return engine.run()


__all__ = [
    "AUTO_LINK_THRESHOLD",
    "REVIEW_THRESHOLD",
    "OpenVehicle",
    "AssociationEngine",
    "run_association",
]