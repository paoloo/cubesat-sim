"""Dimensionless synthetic pass geometry, with no real orbit or location."""

from __future__ import annotations

import numpy as np


def elevation_profile(sample_count: int, max_elevation_deg: float = 70.0) -> np.ndarray:
    """Smooth horizon-to-horizon elevation proxy."""
    phase = np.linspace(0.0, np.pi, sample_count, endpoint=True)
    return max_elevation_deg * np.sin(phase)


def slant_range_km(
    elevation_deg: np.ndarray,
    altitude_km: float = 550.0,
    earth_radius_km: float = 6371.0,
) -> np.ndarray:
    """Spherical-Earth slant range for a fictitious LEO pass."""
    elevation = np.deg2rad(np.asarray(elevation_deg, dtype=float))
    return -earth_radius_km * np.sin(elevation) + np.sqrt(
        (earth_radius_km * np.sin(elevation)) ** 2
        + 2 * earth_radius_km * altitude_km
        + altitude_km**2
    )


def snr_profile(
    sample_count: int, peak_snr_db: float, altitude_km: float = 550.0
) -> np.ndarray:
    """Peak SNR minus relative free-space and bounded low-elevation losses."""
    elevation = elevation_profile(sample_count)
    ranges = slant_range_km(elevation, altitude_km)
    free_space_relative = 20.0 * np.log10(ranges / altitude_km)
    sin_elevation = np.sin(np.deg2rad(np.maximum(elevation, 5.0)))
    excess = np.minimum(3.0, 0.25 * (1.0 / sin_elevation - 1.0))
    return peak_snr_db - free_space_relative - excess


def doppler_profile(sample_count: int, peak_cycles_per_sample: float) -> np.ndarray:
    """Normalized Doppler proxy derived from the fictitious pass range rate."""
    if sample_count < 2 or peak_cycles_per_sample == 0:
        return np.zeros(sample_count)
    ranges = slant_range_km(elevation_profile(sample_count))
    rate = np.gradient(ranges)
    scale = max(float(np.max(np.abs(rate))), np.finfo(float).eps)
    return -peak_cycles_per_sample * rate / scale


def snr_at_fraction(
    pass_fraction: float,
    peak_snr_db: float,
    altitude_km: float = 550.0,
    max_elevation_deg: float = 70.0,
) -> float:
    """Local SNR at a normalized instant in a fictitious pass."""
    if not 0.0 <= pass_fraction <= 1.0:
        raise ValueError("pass_fraction must be in [0,1]")
    elevation = max_elevation_deg * np.sin(np.pi * pass_fraction)
    distance = float(slant_range_km(np.array([elevation]), altitude_km)[0])
    free_space_relative = 20.0 * np.log10(distance / altitude_km)
    sin_elevation = np.sin(np.deg2rad(max(elevation, 5.0)))
    excess = min(3.0, 0.25 * (1.0 / sin_elevation - 1.0))
    return float(peak_snr_db - free_space_relative - excess)


def doppler_at_fraction(pass_fraction: float, peak_cycles_per_sample: float) -> float:
    """Interpolate the range-rate-derived Doppler at a normalized pass instant."""
    if not 0.0 <= pass_fraction <= 1.0:
        raise ValueError("pass_fraction must be in [0,1]")
    grid = np.linspace(0.0, 1.0, 1025)
    profile = doppler_profile(grid.size, peak_cycles_per_sample)
    return float(np.interp(pass_fraction, grid, profile))
