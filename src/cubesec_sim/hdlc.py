"""Clean-room HDLC primitives used by the synthetic AX.25 profile."""

from __future__ import annotations

import numpy as np


def crc16_x25(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0x8408 if crc & 1 else crc >> 1
    return crc ^ 0xFFFF


def append_fcs(data: bytes) -> bytes:
    return data + crc16_x25(data).to_bytes(2, "little")


def check_fcs(data: bytes) -> bool:
    return len(data) >= 2 and crc16_x25(data[:-2]) == int.from_bytes(
        data[-2:], "little"
    )


def bytes_to_bits(data: bytes) -> np.ndarray:
    raw = np.frombuffer(data, dtype=np.uint8)
    return np.unpackbits(raw, bitorder="little")


def bits_to_bytes(bits: np.ndarray) -> bytes:
    bits = np.asarray(bits, dtype=np.uint8)
    if bits.size % 8:
        raise ValueError("bit count must be byte aligned")
    return np.packbits(bits, bitorder="little").tobytes()


def bit_stuff(bits: np.ndarray) -> np.ndarray:
    output: list[int] = []
    ones = 0
    for bit in np.asarray(bits, dtype=np.uint8):
        value = int(bit)
        output.append(value)
        ones = ones + 1 if value else 0
        if ones == 5:
            output.append(0)
            ones = 0
    return np.asarray(output, dtype=np.uint8)


def bit_unstuff(bits: np.ndarray) -> np.ndarray:
    output: list[int] = []
    ones = 0
    i = 0
    raw = np.asarray(bits, dtype=np.uint8)
    while i < raw.size:
        value = int(raw[i])
        output.append(value)
        ones = ones + 1 if value else 0
        i += 1
        if ones == 5:
            if i >= raw.size or raw[i] != 0:
                raise ValueError("invalid HDLC stuffing")
            i += 1
            ones = 0
    return np.asarray(output, dtype=np.uint8)


def nrzi_encode(bits: np.ndarray, initial: int = 1) -> np.ndarray:
    level = initial
    out = []
    for bit in np.asarray(bits, dtype=np.uint8):
        if bit == 0:
            level ^= 1
        out.append(level)
    return np.asarray(out, dtype=np.uint8)


def nrzi_decode(levels: np.ndarray, initial: int = 1) -> np.ndarray:
    previous = initial
    out = []
    for level in np.asarray(levels, dtype=np.uint8):
        out.append(1 if level == previous else 0)
        previous = int(level)
    return np.asarray(out, dtype=np.uint8)
