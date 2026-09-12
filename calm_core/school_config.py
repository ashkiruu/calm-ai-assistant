"""Validation and deterministic lookup for school-local operational values."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE = ROOT / "config" / "school_profile.demo.json"

VALID_PROFILE_STATUSES = {
    "DEMO_PLACEHOLDER_NOT_SCHOOL_APPROVED",
    "SCHOOL_APPROVED",
    "SUSPENDED",
}
VALID_ROUTE_STATES = {"OPEN", "BLOCKED", "CLOSED", "UNKNOWN"}


class SchoolConfigError(RuntimeError):
    """Raised when local operational configuration is internally inconsistent."""


@dataclass(frozen=True)
class RouteResolution:
    requested_route_id: str | None
    selected_route_id: str | None
    assembly_zone_id: str | None
    status: str
    used_alternate: bool
    movement_authorized: bool
    reason_code: str


class SchoolProfile:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or DEFAULT_PROFILE
        with self.path.open(encoding="utf-8") as stream:
            self.data: dict[str, Any] = json.load(stream)
        self._validate()
        self.alarms = {
            item["alarm_id"]: item for item in self.data.get("alarms", [])
        }
        self.routes = {
            item["route_id"]: item for item in self.data.get("routes", [])
        }
        self.assembly_areas = {
            item["zone_id"]: item
            for item in self.data.get("assembly_areas", [])
        }

    def _validate(self) -> None:
        status = self.data.get("status")
        if status not in VALID_PROFILE_STATUSES:
            raise SchoolConfigError(f"Unknown school profile status: {status!r}")
        if (
            status != "SCHOOL_APPROVED"
            and self.data.get("valid_for_real_emergency") is True
        ):
            raise SchoolConfigError(
                "An unapproved school profile cannot be valid for real emergencies"
            )

        self._require_unique("alarms", "alarm_id")
        self._require_unique("routes", "route_id")
        self._require_unique("assembly_areas", "zone_id")

        route_ids = {
            item["route_id"] for item in self.data.get("routes", [])
        }
        assembly_ids = {
            item["zone_id"] for item in self.data.get("assembly_areas", [])
        }
        for route in self.data.get("routes", []):
            if route.get("status") not in VALID_ROUTE_STATES:
                raise SchoolConfigError(
                    f"Route {route['route_id']} has an invalid status"
                )
            if route.get("to_assembly_zone_id") not in assembly_ids:
                raise SchoolConfigError(
                    f"Route {route['route_id']} has an unknown assembly area"
                )
            alternate = route.get("alternate_route_id")
            if alternate and alternate not in route_ids:
                raise SchoolConfigError(
                    f"Route {route['route_id']} has an unknown alternate"
                )

        reunification = self.data.get("reunification", {})
        if reunification.get("release_only_to_authorized_adult") is not True:
            raise SchoolConfigError(
                "Reunification must require an authorized adult"
            )
        prohibited = set(reunification.get("prohibited_storage", []))
        if not {"child_name", "guardian_name", "guardian_contact_details"} <= prohibited:
            raise SchoolConfigError(
                "School profile must prohibit identity/contact storage by CALM"
            )

    def _require_unique(self, collection: str, identifier: str) -> None:
        values = [item.get(identifier) for item in self.data.get(collection, [])]
        if any(not value for value in values) or len(values) != len(set(values)):
            raise SchoolConfigError(
                f"{collection} must have unique, non-empty {identifier} values"
            )

    @property
    def status(self) -> dict[str, Any]:
        return {
            "profile_id": self.data["profile_id"],
            "status": self.data["status"],
            "valid_for_real_emergency": self.data["valid_for_real_emergency"],
            "school_drrm_approved": self.data["review"][
                "school_drrm_approved"
            ],
            "ui_banner": (
                None
                if self.data["status"] == "SCHOOL_APPROVED"
                else "DEMO DATA - NOT SCHOOL APPROVED"
            ),
        }

    def alarm(self, alarm_id: str | None) -> dict[str, Any] | None:
        if not alarm_id:
            return None
        return self.alarms.get(alarm_id)

    def resolve_route(
        self,
        route_id: str | None,
        *,
        from_zone_id: str | None,
        runtime_route_states: dict[str, str] | None = None,
    ) -> RouteResolution:
        """Select only a configured OPEN route or its configured OPEN alternate."""

        if not route_id:
            return RouteResolution(
                None, None, None, "UNKNOWN", False, False, "ROUTE_NOT_PROVIDED"
            )
        route = self.routes.get(route_id)
        if not route:
            return RouteResolution(
                route_id, None, None, "UNKNOWN", False, False, "ROUTE_NOT_CONFIGURED"
            )
        if from_zone_id and route["from_zone_id"] != from_zone_id:
            return RouteResolution(
                route_id,
                None,
                None,
                "UNKNOWN",
                False,
                False,
                "ROUTE_WRONG_ORIGIN",
            )

        states = runtime_route_states or {}
        simulation_profile = (
            self.data["status"] == "DEMO_PLACEHOLDER_NOT_SCHOOL_APPROVED"
        )
        primary_status = states.get(
            route_id, route["status"] if simulation_profile else "UNKNOWN"
        )
        if primary_status == "OPEN":
            return RouteResolution(
                route_id,
                route_id,
                route["to_assembly_zone_id"],
                primary_status,
                False,
                True,
                "ROUTE_OPEN",
            )

        alternate_id = route.get("alternate_route_id")
        alternate = self.routes.get(alternate_id) if alternate_id else None
        if alternate:
            alternate_status = states.get(
                alternate_id,
                alternate["status"] if simulation_profile else "UNKNOWN",
            )
            if (
                alternate_status == "OPEN"
                and (not from_zone_id or alternate["from_zone_id"] == from_zone_id)
            ):
                return RouteResolution(
                    route_id,
                    alternate_id,
                    alternate["to_assembly_zone_id"],
                    alternate_status,
                    True,
                    True,
                    "ALTERNATE_ROUTE_OPEN",
                )

        return RouteResolution(
            route_id,
            None,
            None,
            primary_status if primary_status in VALID_ROUTE_STATES else "UNKNOWN",
            False,
            False,
            "NO_APPROVED_OPEN_ROUTE",
        )
