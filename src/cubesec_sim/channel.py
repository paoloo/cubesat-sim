"""Reproducible time-varying complex-baseband channel."""

from __future__ import annotations

import numpy as np

from .config import ChannelConfig
from .geometry import doppler_at_fraction, snr_at_fraction


def derotate(iq: np.ndarray, offset: float) -> np.ndarray:
    phase = 2 * np.pi * offset * np.arange(1, len(iq) + 1)
    return np.asarray(iq) * np.exp(-1j * phase)


def compensate_clock(iq: np.ndarray, ppm: float) -> np.ndarray:
    if ppm == 0 or len(iq) < 2:
        return np.asarray(iq)
    ratio = 1.0 + ppm * 1e-6
    target_x = np.arange(len(iq), dtype=float) / ratio
    source_x = np.arange(len(iq), dtype=float)
    return np.interp(target_x, source_x, iq.real, left=0.0, right=0.0) + 1j * np.interp(
        target_x, source_x, iq.imag, left=0.0, right=0.0
    )


def apply_channel(
    iq: np.ndarray,
    cfg: ChannelConfig,
    rng: np.random.Generator,
    *,
    pass_fraction: float = 0.5,
) -> np.ndarray:
    signal = np.asarray(iq, dtype=np.complex128).copy()
    if cfg.multipath_delay_samples is not None and cfg.multipath_gain:
        positions = np.arange(len(signal), dtype=float) - cfg.multipath_delay_samples
        delayed = np.interp(
            positions, np.arange(len(signal)), signal.real, left=0.0, right=0.0
        ) + 1j * np.interp(
            positions, np.arange(len(signal)), signal.imag, left=0.0, right=0.0
        )
        phase = np.exp(1j * rng.uniform(-np.pi, np.pi))
        signal = signal + cfg.multipath_gain * phase * delayed
    elif len(cfg.multipath_taps) > 1 or cfg.multipath_taps[0] != 1:
        taps = np.asarray(cfg.multipath_taps, dtype=np.complex128).copy()
        if len(taps) > 1:
            # Fixed magnitudes define the cell; seeded phases vary across replications.
            taps[1:] *= np.exp(1j * rng.uniform(-np.pi, np.pi, size=len(taps) - 1))
        signal = np.convolve(signal, taps, mode="full")[: len(signal)]
    if cfg.sample_clock_ppm:
        ratio = 1.0 + cfg.sample_clock_ppm * 1e-6
        old_x = np.arange(len(signal), dtype=float)
        sample_x = np.arange(len(signal), dtype=float) * ratio
        signal = np.interp(
            sample_x, old_x, signal.real, left=0.0, right=0.0
        ) + 1j * np.interp(sample_x, old_x, signal.imag, left=0.0, right=0.0)
    frequency = cfg.cfo_cycles_per_sample + doppler_at_fraction(
        pass_fraction, cfg.doppler_cycles_per_sample
    )
    signal *= np.exp(
        1j
        * (2 * np.pi * frequency * np.arange(1, len(signal) + 1) + cfg.phase_offset_rad)
    )
    signal *= 10.0 ** (cfg.gain_db / 20.0)
    local_snr = snr_at_fraction(pass_fraction, cfg.snr_db)
    power = max(float(np.mean(np.abs(signal) ** 2)), 1e-12)
    sigma = np.sqrt(power / (2.0 * 10.0 ** (local_snr / 10.0)))
    signal += sigma * (rng.normal(size=len(signal)) + 1j * rng.normal(size=len(signal)))
    if cfg.burst_erasure_probability and cfg.burst_length_samples:
        starts = np.flatnonzero(
            rng.random(len(signal))
            < cfg.burst_erasure_probability / cfg.burst_length_samples
        )
        for start in starts:
            signal[start : start + cfg.burst_length_samples] = 0
    if cfg.impulse_probability:
        mask = rng.random(len(signal)) < cfg.impulse_probability
        signal[mask] += cfg.impulse_scale * (
            rng.normal(size=mask.sum()) + 1j * rng.normal(size=mask.sum())
        )
    if cfg.clip_amplitude is not None:
        magnitude = np.abs(signal)
        over = magnitude > cfg.clip_amplitude
        signal[over] *= cfg.clip_amplitude / magnitude[over]
    return signal.astype("<c8")
