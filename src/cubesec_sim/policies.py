"""Receiver policies separated from deterministic signal-processing tools."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol as TypingProtocol

import numpy as np

from .channel import compensate_clock, derotate
from .config import SimulationConfig
from .geometry import doppler_at_fraction
from .modem import demodulate_payload


@dataclass(frozen=True)
class DecodeResult:
    success: bool
    payload: bytes | None
    calls: tuple[str, ...]
    error: str | None = None


class ReceiverPolicy(TypingProtocol):
    name: str

    def decode(
        self,
        iq: np.ndarray,
        cfg: SimulationConfig,
        rng: np.random.Generator,
        *,
        pass_fraction: float = 0.5,
    ) -> DecodeResult: ...


class ScriptedBaseline:
    """Idealized deterministic upper bound using the injected impairment manifest."""

    name = "scripted_manifest_baseline"

    def decode(
        self,
        iq: np.ndarray,
        cfg: SimulationConfig,
        rng: np.random.Generator,
        *,
        pass_fraction: float = 0.5,
    ) -> DecodeResult:
        del rng
        calls = (
            "inspect_manifest",
            "compensate_clock",
            "correct_frequency",
            "decode_frame",
        )
        try:
            corrected = compensate_clock(iq, cfg.channel.sample_clock_ppm)
            local_doppler = doppler_at_fraction(
                pass_fraction, cfg.channel.doppler_cycles_per_sample
            )
            corrected = derotate(
                corrected, cfg.channel.cfo_cycles_per_sample + local_doppler
            )
            corrected *= np.exp(-1j * cfg.channel.phase_offset_rad)
            return DecodeResult(True, demodulate_payload(corrected, cfg), calls)
        except (ValueError, IndexError) as exc:
            return DecodeResult(False, None, calls, str(exc) or type(exc).__name__)


class BoundedSearchPolicy:
    """Agent-like tool orchestration without network/model dependence.

    It observes only IQ and tries a preregistered normalized CFO grid. The policy is
    intentionally replaceable by a logged external agent while tools stay unchanged.
    """

    name = "bounded_blind_search"

    def __init__(
        self, grid: tuple[float, ...] = (-0.01, -0.004, 0.0, 0.004, 0.01)
    ) -> None:
        self.grid = grid

    def decode(
        self,
        iq: np.ndarray,
        cfg: SimulationConfig,
        rng: np.random.Generator,
        *,
        pass_fraction: float = 0.5,
    ) -> DecodeResult:
        del pass_fraction
        del rng
        calls: list[str] = ["estimate_impairments"]
        for candidate in self.grid:
            for phase in (0.0, np.pi):
                calls.extend(("correct_frequency", "resolve_phase", "decode_frame"))
                try:
                    corrected = derotate(iq, candidate) * np.exp(-1j * phase)
                    payload = demodulate_payload(corrected, cfg)
                    return DecodeResult(True, payload, tuple(calls))
                except (ValueError, IndexError):
                    continue
        return DecodeResult(False, None, tuple(calls), "search_exhausted")


class DirectDecodeAblation:
    """Ablation that removes every correction/search tool."""

    name = "ablation_direct_decode"

    def decode(
        self,
        iq: np.ndarray,
        cfg: SimulationConfig,
        rng: np.random.Generator,
        *,
        pass_fraction: float = 0.5,
    ) -> DecodeResult:
        del pass_fraction
        del rng
        try:
            return DecodeResult(True, demodulate_payload(iq, cfg), ("decode_frame",))
        except (ValueError, IndexError) as exc:
            return DecodeResult(
                False, None, ("decode_frame",), str(exc) or type(exc).__name__
            )
