"""Minimal AX.25 UI framing for synthetic, non-radiating experiments."""

from __future__ import annotations

import numpy as np

from .hdlc import (
    append_fcs,
    bit_stuff,
    bit_unstuff,
    bits_to_bytes,
    bytes_to_bits,
    check_fcs,
)
from .safety import validate_callsign

FLAG = bytes_to_bits(b"\x7e")


def encode_address(callsign: str, *, ssid: int = 0, last: bool = False) -> bytes:
    validate_callsign(callsign)
    if not 0 <= ssid <= 15:
        raise ValueError("SSID must be in [0,15]")
    padded = callsign.ljust(6)
    return bytes(ord(char) << 1 for char in padded) + bytes(
        [0x60 | (ssid << 1) | int(last)]
    )


def decode_address(data: bytes) -> tuple[str, int, bool]:
    if len(data) != 7:
        raise ValueError("AX.25 address is seven bytes")
    callsign = "".join(chr(x >> 1) for x in data[:6]).rstrip()
    validate_callsign(callsign)
    return callsign, (data[6] >> 1) & 0x0F, bool(data[6] & 1)


def encode_ui(
    payload: bytes, source: str = "SIM001", destination: str = "SIMGS"
) -> np.ndarray:
    body = (
        encode_address(destination)
        + encode_address(source, last=True)
        + b"\x03\xf0"
        + payload
    )
    stuffed = bit_stuff(bytes_to_bits(append_fcs(body)))
    return np.concatenate((FLAG, stuffed, FLAG))


def decode_ui(bits: np.ndarray) -> dict[str, object]:
    raw = np.asarray(bits, dtype=np.uint8)
    if (
        raw.size < 16
        or not np.array_equal(raw[:8], FLAG)
        or not np.array_equal(raw[-8:], FLAG)
    ):
        raise ValueError("missing AX.25 flags")
    frame = bits_to_bytes(bit_unstuff(raw[8:-8]))
    if not check_fcs(frame) or len(frame) < 18:
        raise ValueError("invalid AX.25 FCS or length")
    dst, _, _ = decode_address(frame[:7])
    src, _, last = decode_address(frame[7:14])
    if not last or frame[14:16] != b"\x03\xf0":
        raise ValueError("unsupported AX.25 profile")
    return {"source": src, "destination": dst, "payload": frame[16:-2]}
