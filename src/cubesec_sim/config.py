"""Typed, serializable simulation configuration."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

from .safety import validate_callsign, validate_safe


class Protocol(str, Enum):
    AX25_AFSK = "AX25_AFSK"
    CCSDS_BPSK = "CCSDS_BPSK"


@dataclass(frozen=True)
class ChannelConfig:
    snr_db: float = 8.0
    doppler_cycles_per_sample: float = 0.0
    cfo_cycles_per_sample: float = 0.0
    sample_clock_ppm: float = 0.0
    gain_db: float = 0.0
    phase_offset_rad: float = 0.0
    burst_erasure_probability: float = 0.0
    burst_length_samples: int = 0
    impulse_probability: float = 0.0
    impulse_scale: float = 5.0
    multipath_taps: tuple[complex, ...] = (1 + 0j,)
    multipath_delay_samples: float | None = None
    multipath_gain: float = 0.0
    clip_amplitude: float | None = None

    def __post_init__(self) -> None:
        numbers = (
            self.snr_db,
            self.doppler_cycles_per_sample,
            self.cfo_cycles_per_sample,
            self.sample_clock_ppm,
            self.gain_db,
            self.phase_offset_rad,
            self.impulse_scale,
            self.multipath_gain,
        )
        if not all(math.isfinite(float(x)) for x in numbers):
            raise ValueError("channel values must be finite")
        if (
            abs(self.doppler_cycles_per_sample) > 0.25
            or abs(self.cfo_cycles_per_sample) > 0.25
        ):
            raise ValueError("normalized offsets must be within +/-0.25 cycles/sample")
        if abs(self.phase_offset_rad) > math.pi:
            raise ValueError("phase_offset_rad must be within +/-pi")
        for name, value in (
            ("burst_erasure_probability", self.burst_erasure_probability),
            ("impulse_probability", self.impulse_probability),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0,1]")
        if self.burst_length_samples < 0 or self.impulse_scale < 0:
            raise ValueError("lengths/scales cannot be negative")
        if not self.multipath_taps or not all(
            math.isfinite(x.real) and math.isfinite(x.imag) for x in self.multipath_taps
        ):
            raise ValueError("multipath taps must be non-empty and finite")
        if (
            self.multipath_delay_samples is not None
            and self.multipath_delay_samples <= 0
        ):
            raise ValueError("multipath_delay_samples must be positive")
        if self.multipath_gain < 0:
            raise ValueError("multipath_gain cannot be negative")
        if self.clip_amplitude is not None and self.clip_amplitude <= 0:
            raise ValueError("clip_amplitude must be positive")


@dataclass(frozen=True)
class SimulationConfig:
    mission_id: str = "SIM-CUBE-01"
    source_callsign: str = "SIM001"
    destination_callsign: str = "SIMGS"
    protocol: Protocol = Protocol.AX25_AFSK
    sample_rate: int = 9600
    symbol_rate: int = 1200
    master_seed: int = 20260824
    repetitions: int = 30
    frames_per_run: int = 8
    payload_bytes: int = 48
    pass_seconds: float = 12.0
    channel: ChannelConfig = field(default_factory=ChannelConfig)

    def __post_init__(self) -> None:
        validate_safe(asdict(self))
        validate_callsign(self.source_callsign)
        validate_callsign(self.destination_callsign)
        if (
            self.sample_rate <= 0
            or self.symbol_rate <= 0
            or self.sample_rate % self.symbol_rate
        ):
            raise ValueError(
                "sample_rate must be a positive integer multiple of symbol_rate"
            )
        if self.master_seed < 0 or self.repetitions <= 0 or self.frames_per_run <= 0:
            raise ValueError("seed must be nonnegative and counts positive")
        if not 1 <= self.payload_bytes <= 512 or self.pass_seconds <= 0:
            raise ValueError("payload size or pass duration out of bounds")

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["protocol"] = self.protocol.value
        data["channel"]["multipath_taps"] = [
            [x.real, x.imag] for x in self.channel.multipath_taps
        ]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SimulationConfig:
        copy = json.loads(json.dumps(data))
        channel = copy.pop("channel", {})
        channel["multipath_taps"] = tuple(
            complex(*x) for x in channel.get("multipath_taps", [[1.0, 0.0]])
        )
        return cls(
            protocol=Protocol(copy.pop("protocol")),
            channel=ChannelConfig(**channel),
            **copy,
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)
