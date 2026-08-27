"""Seven end-to-end scenarios operating on one spacecraft state."""

from __future__ import annotations

from dataclasses import asdict
from datetime import timedelta
import json
import math
from pathlib import Path

import numpy as np

from .core import Context, ScenarioResult
from .dashboard import Dashboard
from .orbit import Antenna, GroundStation, Propagator, TLE, tle_checksum
from .protocols import AuthenticationError, FrameError, ReplayError, SpacePacket, crc16_ccitt_false
from .radio import decode_afsk, decode_audio, synthesize_afsk
from .spacecraft import APID_PING, APID_RESPONSE


def reference_tle() -> TLE:
    """Synthetic 3U teaching orbit; identifier 99990 is not operational."""
    base1 = "1 99990U 26001A   26238.00000000  .00000000  00000-0  00000-0 0  999"
    base2 = "2 99990  51.6000 120.0000 0005000  45.0000 315.0000 15.20000000    0"
    line1, line2 = base1 + str(tle_checksum(base1)), base2 + str(tle_checksum(base2))
    return TLE.parse(line1, line2)


class VisibilityScenario:
    scenario_id = "01_visibility"
    def execute(self, ctx: Context) -> ScenarioResult:
        tle, station = reference_tle(), GroundStation(-3.7319, -38.5267, 20)
        propagator = Propagator(tle); end = ctx.clock.now() + timedelta(hours=24)
        passes = propagator.passes(station, ctx.clock.now(), end, mask_deg=5)
        checks = {
            "pass_found": bool(passes),
            "ordered_events": all(p.aos < p.tca < p.los for p in passes),
            "above_mask": all(p.max_elevation_deg >= 5 for p in passes),
        }
        ctx.bus.publish("scenario.visibility", "ground", backend=propagator.backend, passes=len(passes))
        return ScenarioResult(self.scenario_id, all(checks.values()), checks, {"passes": len(passes), "max_elevation_deg": max((p.max_elevation_deg for p in passes), default=None)}, {"backend": propagator.backend, "tle_epoch": tle.epoch.isoformat(), "passes": [asdict(p) for p in passes]})


class SpacePacketScenario:
    scenario_id = "02_space_packet"
    def execute(self, ctx: Context) -> ScenarioResult:
        request = SpacePacket(APID_PING, 7, json.dumps({"txid": "tx-ping-0001"}, sort_keys=True).encode())
        raw = request.serialize(); response = SpacePacket.parse(ctx.spacecraft.handle_packet(raw)); body = json.loads(response.data)
        exact_header = raw[:6].hex() == "1001c0070017"
        checks = {"exact_primary_header": exact_header, "response_apid": response.apid == APID_RESPONSE, "correlated": body["txid"] == "tx-ping-0001", "pong": body["reply"] == "pong"}
        return ScenarioResult(self.scenario_id, all(checks.values()), checks, {"command_bytes": len(raw), "response_bytes": len(response.serialize())}, {"command_hex": raw.hex(), "response": body})


class StatefulScenario:
    scenario_id = "03_stateful_session"
    def execute(self, ctx: Context) -> ScenarioResult:
        sid = "teaching-session"
        premature_denied = False
        try: ctx.spacecraft.request_flag(sid, 0)
        except PermissionError: premature_denied = True
        hint = ctx.spacecraft.counter_hint(sid); candidates = [(hint["lower"] + i) % ctx.spacecraft.counter_modulus for i in range(5)]
        accepted = next(counter for counter in candidates if ctx.spacecraft.sync_counter(sid, counter)[0])
        flag = ctx.spacecraft.request_flag(sid, (accepted+1) % ctx.spacecraft.counter_modulus)
        replay_ok, replay_reason = ctx.spacecraft.sync_counter(sid, accepted)
        checks = {"premature_denied": premature_denied, "synchronized": ctx.spacecraft.session(sid).synced, "flag_granted": flag.startswith("SIM{") and flag.endswith("}"), "replay_rejected": not replay_ok and replay_reason == "replay"}
        return ScenarioResult(self.scenario_id, all(checks.values()), checks, {"attempts": candidates.index(accepted)+1, "counter": accepted}, {"session_id": sid, "hint": hint, "flag_sha256_prefix": __import__("hashlib").sha256(flag.encode()).hexdigest()[:16]})


class ProtectedTMScenario:
    scenario_id = "04_protected_tm"
    def execute(self, ctx: Context) -> ScenarioResult:
        sa = ctx.spacecraft.security; packet = SpacePacket(2, 8, b"protected-status", is_command=False).serialize()
        raw = sa.encode(packet, master_count=3, virtual_count=9, anti_replay=1); decoded = sa.decode(raw)
        replay_rejected = False
        try: sa.decode(raw)
        except ReplayError: replay_rejected = True
        fecf_rejected = False
        corrupt = bytearray(raw); corrupt[-1] ^= 1
        try: sa.decode(bytes(corrupt), enforce_replay=False)
        except FrameError: fecf_rejected = True
        authentication_rejected = False
        corrupt = bytearray(raw); corrupt[17] ^= 1; corrupt[-2:] = crc16_ccitt_false(corrupt[:-2]).to_bytes(2, "big")
        try: sa.decode(bytes(corrupt), enforce_replay=False)
        except AuthenticationError: authentication_rejected = True
        checks = {"payload_roundtrip": decoded.payload == packet, "fecf_valid": crc16_ccitt_false(raw[:-2]) == int.from_bytes(raw[-2:], "big"), "replay_rejected": replay_rejected, "fecf_corruption_rejected": fecf_rejected, "authentication_rejected": authentication_rejected}
        return ScenarioResult(self.scenario_id, all(checks.values()), checks, {"frame_bytes": len(raw), "anti_replay": decoded.anti_replay}, {"profile": "SIM-TM-AES256-GCM-v1", "frame_sha256": __import__("hashlib").sha256(raw).hexdigest()})


class TrackingScenario:
    scenario_id = "05_antenna_tracking"
    def execute(self, ctx: Context) -> ScenarioResult:
        prop, station = Propagator(reference_tle()), GroundStation(-3.7319, -38.5267, 20)
        passes = prop.passes(station, ctx.clock.now(), ctx.clock.now()+timedelta(hours=24), 5)
        if not passes: return ScenarioResult(self.scenario_id, False, {"pass_found": False}, {}, {}, "no pass")
        selected, antenna, errors, samples = passes[0], Antenna(max_speed_deg_s=35, max_acceleration_deg_s2=70), [], []
        t = selected.aos; first = prop.look(station, t); antenna.azimuth_deg, antenna.elevation_deg = first.azimuth_deg, max(0, first.elevation_deg); commanded = first
        while t <= selected.los:
            look = prop.look(station, t); antenna.update(commanded.azimuth_deg, commanded.elevation_deg, 1)
            error = math.hypot(Antenna._az_error(look.azimuth_deg, antenna.azimuth_deg), look.elevation_deg-antenna.elevation_deg); errors.append(error); commanded = look
            samples.append({"time": t.isoformat(), "target_azimuth_deg": look.azimuth_deg, "target_elevation_deg": look.elevation_deg, "range_km": look.range_km, "doppler_hz": look.doppler_hz, "error_deg": error})
            t += timedelta(seconds=1)
        rms = math.sqrt(float(np.mean(np.square(errors)))); maximum = max(errors)
        checks = {"pass_found": True, "finite_samples": all(math.isfinite(x) for x in errors), "rms_below_5_deg": rms < 5, "max_below_15_deg": maximum < 15}
        ctx.bus.publish("scenario.tracking", "antenna", samples=len(samples), rms_error_deg=rms)
        return ScenarioResult(self.scenario_id, all(checks.values()), checks, {"samples": len(samples), "rms_error_deg": rms, "max_error_deg": maximum}, {"backend": prop.backend, "first_samples": samples[:5], "last_samples": samples[-5:]})


class DashboardScenario:
    scenario_id = "06_dashboard_lab"
    def execute(self, ctx: Context) -> ScenarioResult:
        secret = __import__("hashlib").sha256(f"dashboard:{ctx.seed}".encode()).digest()
        vulnerable = Dashboard(ctx.spacecraft, profile="vulnerable", secret=secret); token = vulnerable.login("viewer"); altered = vulnerable.alter_claim_for_lab(token, "operator")
        before = ctx.spacecraft.state.camera.captures; receipt = vulnerable.camera_point(altered, 120, 35); after_vulnerable = ctx.spacecraft.state.camera.captures
        patched = Dashboard(ctx.spacecraft, profile="patched", secret=secret); denied = False
        try: patched.camera_point(patched.alter_claim_for_lab(patched.login("viewer"), "operator"), 121, 36)
        except PermissionError: denied = True
        checks = {"vulnerable_path_demonstrated": after_vulnerable == before+1, "patched_path_denied": denied, "patched_state_unchanged": ctx.spacecraft.state.camera.captures == after_vulnerable, "shared_state_updated": ctx.spacecraft.state.storage_used_mb > 32}
        return ScenarioResult(self.scenario_id, all(checks.values()), checks, {"captures": ctx.spacecraft.state.camera.captures, "storage_used_mb": ctx.spacecraft.state.storage_used_mb}, {"receipt": receipt, "vulnerable_audit": vulnerable.audit, "patched_audit": patched.audit})


class AFSKScenario:
    scenario_id = "07_afsk_capture"
    def __init__(self, capture_path: Path | None = None): self.capture_path = capture_path
    def execute(self, ctx: Context) -> ScenarioResult:
        expected = b"SIMUL-AFSK1200-PASSIVE"
        if self.capture_path:
            reference: set[bytes] = set()
            if self.capture_path.is_dir():
                manifest = json.loads((self.capture_path/"manifest.json").read_text())
                base = self.capture_path.resolve(); fixture_files = []
                for item in manifest.get("files", []):
                    path = (self.capture_path/item["path"]).resolve()
                    if not path.is_relative_to(base): raise ValueError("fixture manifest path escapes its directory")
                    data = path.read_bytes()
                    if __import__("hashlib").sha256(data).hexdigest() != item["sha256"] or len(data) != item["bytes"]: raise ValueError(f"fixture integrity failure: {item['path']}")
                    fixture_files.append(path)
                audio_files = [path for path in fixture_files if path.name.startswith("audio.")]
                if len(audio_files) != 1: raise ValueError("fixture must contain exactly one audio file")
                audio_path = audio_files[0]; reference = {path.read_bytes() for path in fixture_files if path.suffix == ".bin"}
                kind = "satnogs-passive-fixture" if manifest.get("provider") == "SatNOGS Network" else "materialized-synthetic-fixture"
                provenance = {"kind": kind, "manifest": manifest}
            else:
                audio_path = self.capture_path; provenance = {"kind": "user-supplied-passive-audio", "path": str(audio_path)}
            frames = decode_audio(audio_path); matches = sum(frame.raw_frame in reference or frame.raw_frame[:-2] in reference for frame in frames)
            payload_check = bool(frames) and (not reference or matches > 0)
        else:
            samples = synthesize_afsk(expected, leading_samples=17); frames = decode_afsk(samples, 9600)
            provenance = {"kind": "synthetic-independent-fixture", "sample_rate": 9600, "leading_samples": 17}; payload_check = any(f.payload == expected for f in frames); matches = 0
        checks = {"frame_recovered": bool(frames), "fcs_valid_frame": payload_check, "timing_acquired": bool(frames) and frames[0].timestamp_s > 0}
        if self.capture_path and reference: checks["external_reference_match"] = matches > 0
        evidence = {"provenance": provenance, "frames": [{**asdict(frame), "payload": frame.payload.hex(), "raw_frame": frame.raw_frame.hex()} for frame in frames]}
        return ScenarioResult(self.scenario_id, all(checks.values()), checks, {"valid_frames": len(frames), "reference_matches": matches, "confidence": frames[0].confidence if frames else 0}, evidence)


SCENARIOS = {
    "visibility": VisibilityScenario,
    "space-packet": SpacePacketScenario,
    "stateful": StatefulScenario,
    "protected-tm": ProtectedTMScenario,
    "tracking": TrackingScenario,
    "dashboard": DashboardScenario,
    "afsk": AFSKScenario,
}
