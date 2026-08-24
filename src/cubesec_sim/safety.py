"""Safety boundary: reject configurations that could address real systems."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from pathlib import PurePath
from typing import Any

_URL = re.compile(r"(?:https?|ftp|ssh|tcp|udp)://", re.IGNORECASE)
_TLE = re.compile(r"^[12] \d{5}[A-Z ]", re.MULTILINE)
_DEVICE = re.compile(
    r"(?:^|[/\\])dev[/\\]|COM\d+|rtl[-_ ]?sdr|hackrf|plutosdr", re.IGNORECASE
)
_FORBIDDEN_KEYS = {
    "latitude",
    "longitude",
    "lat",
    "lon",
    "center_frequency",
    "rf_frequency",
    "tuning_frequency",
}
_FORBIDDEN_OPS = ("transmit", "uplink", "command", "replay_attack", "jam", "spoof")


def validate_callsign(value: str) -> str:
    """Accept only unmistakably synthetic AX.25 address text."""
    if not re.fullmatch(r"SIM[A-Z0-9]{0,3}", value):
        raise ValueError("AX.25 callsigns must match SIM[A-Z0-9]{0,3}")
    return value


def validate_safe(value: Any, *, key: str = "root") -> None:
    """Recursively validate an object against the offline-only boundary."""
    lowered = key.lower()
    if lowered in _FORBIDDEN_KEYS:
        raise ValueError(f"real-world locator or RF key is prohibited: {key}")
    if isinstance(value, Mapping):
        for child_key, child in value.items():
            validate_safe(child, key=str(child_key))
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            validate_safe(child, key=f"{key}[{index}]")
        return
    if not isinstance(value, str):
        return
    if _URL.search(value) or _TLE.search(value) or _DEVICE.search(value):
        raise ValueError(
            f"external endpoint, orbital element, or RF device prohibited at {key}"
        )
    if lowered in {"operation", "action", "tool"}:
        op = value.lower()
        if not op.startswith("sim_") and any(term in op for term in _FORBIDDEN_OPS):
            raise ValueError(f"operation outside synthetic simulator boundary: {value}")
    if lowered in {"mission_id", "spacecraft_id"} and not value.startswith("SIM-"):
        raise ValueError(f"{key} must begin with SIM-")
    if lowered in {"source_callsign", "destination_callsign", "callsign"}:
        validate_callsign(value)


def safe_output_path(path: str | PurePath) -> PurePath:
    """Reject device paths; output-directory containment is checked by the caller."""
    candidate = PurePath(path)
    validate_safe(str(candidate), key="output_path")
    return candidate
