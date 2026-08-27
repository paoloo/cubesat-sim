"""Space Packet, CRC and authenticated TM laboratory profile."""

from __future__ import annotations

from dataclasses import dataclass
import struct

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class PacketError(ValueError): pass
class FrameError(ValueError): pass
class AuthenticationError(FrameError): pass
class ReplayError(FrameError): pass


def crc16_ccitt_false(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


@dataclass(frozen=True)
class SpacePacket:
    apid: int
    sequence_count: int
    data: bytes
    is_command: bool = True
    secondary_header: bool = False
    sequence_flags: int = 0b11

    def serialize(self) -> bytes:
        if not 0 <= self.apid <= 0x7FF: raise PacketError("APID outside 11-bit range")
        if not 0 <= self.sequence_count <= 0x3FFF: raise PacketError("sequence count outside 14-bit range")
        if not 0 <= self.sequence_flags <= 3: raise PacketError("sequence flags outside 2-bit range")
        if not 1 <= len(self.data) <= 65536: raise PacketError("packet data length outside profile")
        first = (int(self.is_command) << 12) | (int(self.secondary_header) << 11) | self.apid
        second = (self.sequence_flags << 14) | self.sequence_count
        return struct.pack(">HHH", first, second, len(self.data) - 1) + self.data

    @classmethod
    def parse(cls, raw: bytes) -> "SpacePacket":
        if len(raw) < 7: raise PacketError("packet too short")
        first, second, length = struct.unpack(">HHH", raw[:6])
        if first >> 13: raise PacketError("unsupported packet version")
        if len(raw) != length + 7: raise PacketError("packet data length mismatch")
        return cls(first & 0x7FF, second & 0x3FFF, raw[6:], bool(first & 0x1000), bool(first & 0x0800), second >> 14)


@dataclass(frozen=True)
class TMFrame:
    spacecraft_id: int
    vcid: int
    master_count: int
    virtual_count: int
    spi: int
    anti_replay: int
    payload: bytes


class SecurityAssociation:
    """AES-256-GCM protected fixed TM lab profile with a CRC FECF."""

    def __init__(self, spi: int, key: bytes):
        if not 0 <= spi <= 0xFFFF or len(key) != 32: raise ValueError("invalid security association")
        self.spi, self._aead, self.highest_received = spi, AESGCM(key), -1

    @staticmethod
    def _nonce(spi: int, anti_replay: int) -> bytes:
        return struct.pack(">HQH", spi, anti_replay, 0)

    def encode(self, payload: bytes, *, spacecraft_id: int = 1, vcid: int = 0, master_count: int = 0, virtual_count: int = 0, anti_replay: int = 0) -> bytes:
        if not 0 <= spacecraft_id <= 0x3FF or not 0 <= vcid <= 7: raise FrameError("invalid TM identity")
        if not 0 <= anti_replay < 1 << 64: raise FrameError("anti-replay counter outside range")
        if len(payload) > 65535: raise FrameError("payload too large")
        primary = struct.pack(">HBB", (spacecraft_id << 4) | (vcid << 1), master_count & 0xFF, virtual_count & 0xFF)
        security = struct.pack(">HQH", self.spi, anti_replay, len(payload))
        ciphertext = self._aead.encrypt(self._nonce(self.spi, anti_replay), payload, primary + security)
        body = primary + security + ciphertext
        return body + crc16_ccitt_false(body).to_bytes(2, "big")

    def decode(self, raw: bytes, *, enforce_replay: bool = True) -> TMFrame:
        if len(raw) < 34: raise FrameError("TM frame too short")
        if crc16_ccitt_false(raw[:-2]) != int.from_bytes(raw[-2:], "big"): raise FrameError("invalid FECF")
        ident, master, virtual = struct.unpack(">HBB", raw[:4])
        spi, replay, length = struct.unpack(">HQH", raw[4:16])
        if spi != self.spi: raise AuthenticationError("unknown SPI")
        if len(raw) != 16 + length + 16 + 2: raise FrameError("TM frame length mismatch")
        if enforce_replay and replay <= self.highest_received: raise ReplayError("replayed protected frame")
        try:
            payload = self._aead.decrypt(self._nonce(spi, replay), raw[16:-2], raw[:16])
        except InvalidTag as exc:
            raise AuthenticationError("authentication failed") from exc
        if enforce_replay: self.highest_received = replay
        return TMFrame((ident >> 4) & 0x3FF, (ident >> 1) & 7, master, virtual, spi, replay, payload)

