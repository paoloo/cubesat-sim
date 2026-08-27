"""WAV PCM AFSK1200 acquisition and AX.25 frame recovery."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import subprocess
import wave

import numpy as np

from ..ax25 import FLAG, encode_ui
from ..hdlc import bit_unstuff, bits_to_bytes, check_fcs, nrzi_decode, nrzi_encode


@dataclass(frozen=True)
class DecodedFrame:
    timestamp_s: float
    source: str
    destination: str
    payload: bytes
    confidence: float
    repeaters: tuple[str, ...] = ()
    raw_frame: bytes = b""


def synthesize_afsk(payload: bytes, *, sample_rate: int = 9600, leading_samples: int = 13) -> np.ndarray:
    if sample_rate % 1200: raise ValueError("sample rate must be a multiple of 1200")
    bits = np.concatenate((FLAG, FLAG, encode_ui(payload), FLAG))
    levels = nrzi_encode(bits); sps = sample_rate // 1200
    tones = np.where(np.repeat(levels, sps) == 1, 1200.0, 2200.0)
    phase = np.cumsum(2*np.pi*tones/sample_rate)
    return np.concatenate((np.zeros(leading_samples), .75*np.sin(phase))).astype(np.float64)


def write_wav(path: Path, samples: np.ndarray, sample_rate: int = 9600) -> None:
    pcm = np.clip(np.asarray(samples), -1, 1); raw = (pcm*32767).astype("<i2").tobytes()
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1); stream.setsampwidth(2); stream.setframerate(sample_rate); stream.writeframes(raw)


def read_wav(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as stream:
        if stream.getnchannels() != 1 or stream.getsampwidth() != 2: raise ValueError("only mono 16-bit PCM WAV is supported")
        rate, raw = stream.getframerate(), stream.readframes(stream.getnframes())
    signal = np.frombuffer(raw, dtype="<i2").astype(np.float64)/32768
    signal -= signal.mean() if signal.size else 0
    return signal, rate


def _decode_ax25(bits: np.ndarray) -> tuple[str, str, tuple[str, ...], bytes, bytes]:
    """Decode a UI frame with the variable AX.25 address field used by APRS."""
    if len(bits) < 16 or not np.array_equal(bits[:8], FLAG) or not np.array_equal(bits[-8:], FLAG):
        raise ValueError("missing AX.25 flags")
    frame = bits_to_bytes(bit_unstuff(bits[8:-8]))
    if len(frame) < 18 or not check_fcs(frame): raise ValueError("invalid AX.25 FCS or length")
    addresses, offset, last = [], 0, False
    while not last:
        if offset + 7 > len(frame) - 4 or len(addresses) >= 10: raise ValueError("invalid AX.25 address chain")
        address = frame[offset:offset+7]
        if any(byte & 1 for byte in address[:6]): raise ValueError("invalid AX.25 shifted address")
        callsign = "".join(chr(byte >> 1) for byte in address[:6]).rstrip()
        if not callsign or any(not (char.isalnum() or char == " ") for char in callsign): raise ValueError("invalid AX.25 callsign")
        ssid, last = (address[6] >> 1) & 0x0F, bool(address[6] & 1)
        addresses.append(callsign + (f"-{ssid}" if ssid else "")); offset += 7
    if len(addresses) < 2 or frame[offset:offset+2] != b"\x03\xf0": raise ValueError("unsupported AX.25 control/PID")
    return addresses[1], addresses[0], tuple(addresses[2:]), frame[offset+2:-2], frame


def _candidates(bits: np.ndarray, timestamp_offset: float, confidence: float) -> list[DecodedFrame]:
    flag = FLAG.tolist(); positions = [i for i in range(max(0, len(bits)-7)) if bits[i:i+8].tolist() == flag]
    found: list[DecodedFrame] = []
    for left, right in zip(positions, positions[1:]):
        if right-left <= 8: continue
        framed = bits[left:right+8]
        try:
            source, destination, repeaters, payload, raw = _decode_ax25(framed)
            found.append(DecodedFrame(timestamp_offset + left/1200, source, destination, payload, confidence, repeaters, raw))
        except ValueError: pass
    return found


def decode_afsk(samples: np.ndarray, sample_rate: int) -> list[DecodedFrame]:
    if sample_rate % 1200: raise ValueError("sample rate must be an integer multiple of 1200")
    signal = np.asarray(samples, dtype=float); sps = sample_rate//1200; n = np.arange(sps)
    best: list[DecodedFrame] = []
    for phase in range(sps):
        count = (len(signal)-phase)//sps
        if count < 16: continue
        blocks = signal[phase:phase+count*sps].reshape(count, sps)
        scores = []
        for tone in (1200.0, 2200.0):
            kernel = np.exp(-2j*np.pi*tone*n/sample_rate); scores.append(np.abs(blocks@kernel))
        levels = (scores[0] >= scores[1]).astype(np.uint8)
        margin = np.abs(scores[0]-scores[1])/(scores[0]+scores[1]+1e-12); conf = float(np.median(margin))
        for initial in (0, 1):
            frames = _candidates(nrzi_decode(levels, initial), phase/sample_rate, conf)
            if len(frames) > len(best) or (len(frames) == len(best) and frames and frames[0].confidence > best[0].confidence): best = frames
    unique: dict[tuple[bytes, str, str], DecodedFrame] = {}
    for frame in best: unique[(frame.payload, frame.source, frame.destination)] = frame
    return list(unique.values())


def decode_wav(path: Path) -> list[DecodedFrame]:
    return decode_afsk(*read_wav(path))


def read_audio(path: Path, sample_rate: int = 9600) -> tuple[np.ndarray, int]:
    """Read WAV directly or decode a passive OGG capture through ffmpeg."""
    if path.suffix.lower() == ".wav": return read_wav(path)
    if path.suffix.lower() not in {".ogg", ".oga"}: raise ValueError("capture must be WAV or OGG audio")
    try:
        completed = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(sample_rate), "-f", "s16le", "-"],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
    except FileNotFoundError as exc: raise RuntimeError("ffmpeg is required for OGG fixtures") from exc
    except subprocess.CalledProcessError as exc: raise ValueError(f"unable to decode audio: {exc.stderr.decode(errors='replace')}") from exc
    signal = np.frombuffer(completed.stdout, dtype="<i2").astype(np.float64)/32768
    signal -= signal.mean() if signal.size else 0
    return signal, sample_rate


def decode_audio(path: Path) -> list[DecodedFrame]:
    return decode_afsk(*read_audio(path))


def generate_synthetic_fixture(output: Path, payload: bytes = b"SIMUL-AFSK1200-CLASSROOM", *, sample_rate: int = 9600, leading_samples: int = 17) -> dict[str, object]:
    """Materialize the deterministic encoder fixture used by the lab."""
    if output.exists(): raise FileExistsError(f"refusing to overwrite {output}")
    output.mkdir(parents=True); audio = output/"audio.wav"
    write_wav(audio, synthesize_afsk(payload, sample_rate=sample_rate, leading_samples=leading_samples), sample_rate)
    digest = hashlib.sha256(audio.read_bytes()).hexdigest()
    manifest = {"schema": 1, "kind": "synthetic-afsk1200", "generator": "CubeSec-Sim 1.0", "sample_rate": sample_rate, "leading_samples": leading_samples, "payload_hex": payload.hex(), "files": [{"path": "audio.wav", "sha256": digest, "bytes": audio.stat().st_size}]}
    (output/"manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    return manifest
