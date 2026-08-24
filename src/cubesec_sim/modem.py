"""Synthetic baseband modems and frame recovery."""

from __future__ import annotations

import numpy as np

from .ax25 import decode_ui, encode_ui
from .ccsds import decode_tm, encode_tm
from .config import Protocol, SimulationConfig
from .hdlc import nrzi_decode, nrzi_encode


def afsk_modulate(levels: np.ndarray, sample_rate: int, symbol_rate: int) -> np.ndarray:
    """Continuous-phase binary FSK at normalized audio/baseband offsets."""
    sps = sample_rate // symbol_rate
    repeated = np.repeat(np.asarray(levels, dtype=np.uint8), sps)
    # Mark is DC after complex downconversion; space is +1000 Hz at default rate.
    delta = min(1000.0 / sample_rate, 0.2)
    increments = 2 * np.pi * np.where(repeated == 1, 0.0, delta)
    phase = np.cumsum(increments, dtype=np.float64)
    return np.exp(1j * phase).astype("<c8")


def afsk_demodulate(iq: np.ndarray, sample_rate: int, symbol_rate: int) -> np.ndarray:
    """Symbol-aligned noncoherent matched-filter detector."""
    sps = sample_rate // symbol_rate
    count = len(iq) // sps
    if count == 0:
        return np.empty(0, dtype=np.uint8)
    blocks = np.asarray(iq[: count * sps]).reshape(count, sps)
    n = np.arange(sps)
    delta = min(1000.0 / sample_rate, 0.2)
    mark = np.abs(np.sum(blocks, axis=1))
    space = np.abs(np.sum(blocks * np.exp(-2j * np.pi * delta * n), axis=1))
    return (mark >= space).astype(np.uint8)


def bpsk_modulate(bits: np.ndarray, samples_per_symbol: int) -> np.ndarray:
    symbols = 2.0 * np.asarray(bits, dtype=np.float32) - 1.0
    return np.repeat(symbols.astype(np.complex64), samples_per_symbol).astype("<c8")


def bpsk_demodulate(iq: np.ndarray, samples_per_symbol: int) -> np.ndarray:
    count = len(iq) // samples_per_symbol
    blocks = np.asarray(iq[: count * samples_per_symbol]).reshape(
        count, samples_per_symbol
    )
    return (blocks.real.mean(axis=1) >= 0).astype(np.uint8)


def modulate_payload(
    payload: bytes, cfg: SimulationConfig, sequence: int = 0
) -> np.ndarray:
    if cfg.protocol is Protocol.AX25_AFSK:
        return afsk_modulate(
            nrzi_encode(
                encode_ui(payload, cfg.source_callsign, cfg.destination_callsign)
            ),
            cfg.sample_rate,
            cfg.symbol_rate,
        )
    return bpsk_modulate(
        encode_tm(payload, sequence=sequence), cfg.sample_rate // cfg.symbol_rate
    )


def demodulate_payload(iq: np.ndarray, cfg: SimulationConfig) -> bytes:
    if cfg.protocol is Protocol.AX25_AFSK:
        levels = afsk_demodulate(iq, cfg.sample_rate, cfg.symbol_rate)
        return decode_ui(nrzi_decode(levels))["payload"]  # type: ignore[return-value]
    return decode_tm(bpsk_demodulate(iq, cfg.sample_rate // cfg.symbol_rate))
