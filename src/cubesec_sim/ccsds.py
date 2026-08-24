"""Bounded CCSDS-inspired TM profile; not a conformance implementation."""

from __future__ import annotations

import numpy as np

from .hdlc import bits_to_bytes, bytes_to_bits

ASM = b"\x1a\xcf\xfc\x1d"
_POLYNOMIALS = (0o171, 0o133)


def _parity(value: int) -> int:
    return value.bit_count() & 1


def convolutional_encode(bits: np.ndarray, terminate: bool = True) -> np.ndarray:
    """Rate-1/2, constraint-length-7 encoder with (171,133) octal generators."""
    source = np.asarray(bits, dtype=np.uint8)
    if terminate:
        source = np.concatenate((source, np.zeros(6, dtype=np.uint8)))
    state = 0
    output = np.empty(source.size * 2, dtype=np.uint8)
    for index, bit in enumerate(source):
        register = ((state << 1) | int(bit)) & 0x7F
        output[2 * index] = _parity(register & _POLYNOMIALS[0])
        output[2 * index + 1] = _parity(register & _POLYNOMIALS[1]) ^ 1
        state = register & 0x3F
    return output


def viterbi_decode(coded: np.ndarray, terminated: bool = True) -> np.ndarray:
    """Hard-decision Viterbi decoder matched to :func:`convolutional_encode`."""
    received = np.asarray(coded, dtype=np.uint8)
    if received.size % 2:
        raise ValueError("convolutional stream must contain symbol pairs")
    steps = received.size // 2
    infinity = steps * 3 + 1
    metrics = np.full(64, infinity, dtype=np.int64)
    metrics[0] = 0
    predecessors = np.zeros((steps, 64), dtype=np.uint8)
    decisions = np.zeros((steps, 64), dtype=np.uint8)
    next_states = np.arange(64, dtype=np.uint8)
    input_bits = next_states & 1
    predecessor0 = next_states >> 1
    predecessor1 = predecessor0 | 32
    register0 = ((predecessor0.astype(np.uint16) << 1) | input_bits) & 0x7F
    register1 = ((predecessor1.astype(np.uint16) << 1) | input_bits) & 0x7F
    expected0 = np.array(
        [
            [_parity(int(reg & polynomial)) for polynomial in _POLYNOMIALS]
            for reg in register0
        ],
        dtype=np.uint8,
    )
    expected1 = np.array(
        [
            [_parity(int(reg & polynomial)) for polynomial in _POLYNOMIALS]
            for reg in register1
        ],
        dtype=np.uint8,
    )
    expected0[:, 1] ^= 1
    expected1[:, 1] ^= 1
    for step in range(steps):
        pair = received[2 * step : 2 * step + 2]
        distance0 = np.count_nonzero(expected0 != pair, axis=1)
        distance1 = np.count_nonzero(expected1 != pair, axis=1)
        candidate0 = metrics[predecessor0] + distance0
        candidate1 = metrics[predecessor1] + distance1
        choose1 = candidate1 < candidate0
        metrics = np.where(choose1, candidate1, candidate0)
        predecessors[step] = np.where(choose1, predecessor1, predecessor0)
        decisions[step] = input_bits
    state = 0 if terminated else int(np.argmin(metrics))
    if metrics[state] >= infinity:
        raise ValueError("no Viterbi path")
    decoded = np.empty(steps, dtype=np.uint8)
    for step in range(steps - 1, -1, -1):
        decoded[step] = decisions[step, state]
        state = int(predecessors[step, state])
    return decoded[:-6] if terminated else decoded


def crc16_ccitt_false(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = (
                ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
            )
    return crc


def randomizer(length: int) -> bytes:
    """CCSDS legacy 255-bit PN sequence, h(x)=x^8+x^7+x^5+x^3+1."""
    state = 0xFF
    out = bytearray()
    for _ in range(length):
        value = 0
        for _ in range(8):
            value = (value << 1) | (state & 1)
            feedback = (state & 0xA9).bit_count() & 1
            state = (state >> 1) | (feedback << 7)
        out.append(value)
    return bytes(out)


def make_space_packet(payload: bytes, apid: int = 1, sequence: int = 0) -> bytes:
    if not 0 <= apid <= 0x7FF or not 0 <= sequence <= 0x3FFF or not payload:
        raise ValueError("invalid synthetic space packet")
    first = apid
    second = 0xC000 | sequence
    return (
        first.to_bytes(2, "big")
        + second.to_bytes(2, "big")
        + (len(payload) - 1).to_bytes(2, "big")
        + payload
    )


def encode_tm(
    payload: bytes, spacecraft_id: int = 1, vcid: int = 0, sequence: int = 0
) -> np.ndarray:
    packet = make_space_packet(payload, sequence=sequence)
    header = ((spacecraft_id & 0x3FF) << 4 | (vcid & 7)).to_bytes(
        2, "big"
    ) + sequence.to_bytes(2, "big")
    frame = header + packet
    frame += crc16_ccitt_false(frame).to_bytes(2, "big")
    pn = randomizer(len(frame))
    randomized = bytes(a ^ b for a, b in zip(frame, pn))
    return np.concatenate(
        (bytes_to_bits(ASM), convolutional_encode(bytes_to_bits(randomized)))
    )


def decode_tm(bits: np.ndarray) -> bytes:
    raw_bits = np.asarray(bits, dtype=np.uint8)
    if raw_bits.size < 32 or bits_to_bytes(raw_bits[:32]) != ASM:
        raise ValueError("missing ASM or short frame")
    randomized_bits = viterbi_decode(raw_bits[32:])
    if randomized_bits.size % 8:
        raise ValueError("decoded TM frame is not byte aligned")
    randomized = bits_to_bytes(randomized_bits)
    if len(randomized) < 4 + 6 + 2:
        raise ValueError("missing ASM or short frame")
    frame = bytes(a ^ b for a, b in zip(randomized, randomizer(len(randomized))))
    if crc16_ccitt_false(frame[:-2]) != int.from_bytes(frame[-2:], "big"):
        raise ValueError("invalid TM frame CRC")
    packet = frame[4:-2]
    expected = int.from_bytes(packet[4:6], "big") + 1
    payload = packet[6:]
    if expected != len(payload):
        raise ValueError("invalid space packet length")
    return payload
