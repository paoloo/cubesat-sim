"""Integrated OBC, EPS, ADCS, COMMS, payload and FDIR mission state."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import hmac
import json
from typing import Any

from .core import Clock, EventBus
from .protocols import PacketError, SecurityAssociation, SpacePacket

APID_PING, APID_STATUS = 0x001, 0x002
APID_COUNTER_SYNC, APID_FLAG, APID_CAMERA, APID_RESPONSE = 0x010, 0x011, 0x020, 0x100


@dataclass
class EPS: battery_wh: float = 28.0; capacity_wh: float = 32.0; solar_w: float = 8.0; load_w: float = 4.0
@dataclass
class ADCS: mode: str = "nadir"; azimuth_deg: float = 0.0; elevation_deg: float = 0.0; target_azimuth_deg: float = 0.0; target_elevation_deg: float = 0.0
@dataclass
class Camera: powered: bool = False; captures: int = 0; last_target: dict[str, float] | None = None
@dataclass
class MissionState:
    mode: str = "nominal"
    uptime_s: float = 0.0
    temperature_c: float = 20.0
    storage_used_mb: float = 32.0
    storage_capacity_mb: float = 2048.0
    comms_frames: int = 0
    obc_resets: int = 0
    watchdog_resets: int = 0
    last_fault: str | None = None
    eps: EPS = field(default_factory=EPS)
    adcs: ADCS = field(default_factory=ADCS)
    camera: Camera = field(default_factory=Camera)


@dataclass
class Session:
    expected_counter: int
    synced: bool = False
    granted: bool = False
    seen: set[int] = field(default_factory=set)


class Spacecraft:
    def __init__(self, clock: Clock, bus: EventBus, run_id: str, seed: int = 20260826):
        self.clock, self.bus, self.run_id = clock, bus, run_id
        self.state, self.sessions, self.counter_modulus = MissionState(), {}, 1 << 14
        self.watchdog_timeout_s, self._last_heartbeat_s = 30.0, 0.0
        self._lab_key = hashlib.sha256(f"SIM-LAB:{seed}".encode()).digest()
        self.security = SecurityAssociation(0x1001, hashlib.sha256(self._lab_key + b"SDLS").digest())
        bus.publish("spacecraft.boot", "obc", mode=self.state.mode)

    def tick(self, seconds: float, *, sunlit: bool = True) -> None:
        if seconds < 0: raise ValueError("seconds must be non-negative")
        eps = self.state.eps
        eps.battery_wh = min(eps.capacity_wh, max(0.0, eps.battery_wh + ((eps.solar_w if sunlit else 0) - eps.load_w) * seconds / 3600))
        self.state.uptime_s += seconds
        target = 24.0 if sunlit else 8.0
        self.state.temperature_c += (target - self.state.temperature_c) * min(1, seconds / 600)
        if eps.battery_wh < 3.2: self.state.mode = "safe"
        self.clock.sleep(seconds)
        self.bus.publish("spacecraft.tick", "scheduler", seconds=seconds, battery_wh=round(eps.battery_wh, 6))
        if self.state.uptime_s - self._last_heartbeat_s > self.watchdog_timeout_s:
            self.reset_obc("watchdog")

    def heartbeat(self) -> None:
        self._last_heartbeat_s = self.state.uptime_s
        self.bus.publish("watchdog.heartbeat", "obc", uptime_s=self.state.uptime_s)

    def reset_obc(self, reason: str) -> None:
        self.state.obc_resets += 1
        if reason == "watchdog": self.state.watchdog_resets += 1
        self.state.last_fault = reason
        self.sessions.clear()
        self._last_heartbeat_s = self.state.uptime_s
        self.bus.publish("spacecraft.reset", "fdir", reason=reason, retained_mission_state=True, sessions_cleared=True)

    def inject_fault(self, fault: str) -> None:
        """Inject one of a bounded set of synthetic teaching faults."""
        if fault == "battery_depleted":
            self.state.eps.battery_wh = 2.0; self.state.mode = "safe"
        elif fault == "thermal_high":
            self.state.temperature_c = 75.0; self.state.mode = "safe"
        elif fault == "comms_reset":
            self.reset_obc("comms_reset")
        else:
            raise ValueError("unsupported synthetic fault")
        self.state.last_fault = fault
        self.bus.publish("fault.injected", "fdir", fault=fault, mode=self.state.mode)

    def telemetry(self) -> dict[str, Any]:
        data = asdict(self.state); data["mission_time"] = self.clock.now().isoformat(); return data

    def session(self, session_id: str) -> Session:
        if not session_id or len(session_id) > 64: raise ValueError("invalid session id")
        if session_id not in self.sessions:
            start = int.from_bytes(hmac.new(self._lab_key, session_id.encode(), hashlib.sha256).digest()[:2], "big") % self.counter_modulus
            self.sessions[session_id] = Session(start)
            self.bus.publish("session.created", "comms", session_id=session_id)
        return self.sessions[session_id]

    def counter_hint(self, session_id: str) -> dict[str, int]:
        state = self.session(session_id)
        return {"lower": (state.expected_counter - 2) % self.counter_modulus, "upper": (state.expected_counter + 2) % self.counter_modulus}

    def sync_counter(self, session_id: str, counter: int) -> tuple[bool, str]:
        state, counter = self.session(session_id), counter % self.counter_modulus
        if counter in state.seen: result = "replay"
        else:
            delta = (counter - state.expected_counter) % self.counter_modulus
            if delta == 0:
                state.seen.add(counter); state.expected_counter = (counter + 1) % self.counter_modulus; state.synced = True; result = "accepted"
            elif delta < self.counter_modulus // 2: result = "future"
            else: result = "old"
        self.bus.publish("session.counter", "comms", session_id=session_id, counter=counter, result=result)
        return result == "accepted", result

    def request_flag(self, session_id: str, counter: int) -> str:
        state = self.session(session_id)
        if not state.synced: raise PermissionError("flag denied: session not synchronized")
        ok, reason = self.sync_counter(session_id, counter)
        if not ok: raise PermissionError(f"flag denied: {reason}")
        state.granted = True
        token = hmac.new(self._lab_key, f"{self.run_id}:{session_id}".encode(), hashlib.sha256).hexdigest()[:24]
        self.bus.publish("session.flag_granted", "obc", session_id=session_id)
        return f"SIM{{{token}}}"

    def point_camera(self, azimuth_deg: float, elevation_deg: float, actor: str) -> dict[str, Any]:
        if self.state.mode == "safe" or self.state.eps.battery_wh < 5: raise RuntimeError("camera unavailable in current power mode")
        if not 0 <= azimuth_deg < 360 or not -20 <= elevation_deg <= 90: raise ValueError("camera target outside synthetic domain")
        adcs, camera = self.state.adcs, self.state.camera
        adcs.mode, adcs.target_azimuth_deg, adcs.target_elevation_deg = "target", azimuth_deg, elevation_deg
        adcs.azimuth_deg, adcs.elevation_deg = azimuth_deg, elevation_deg
        camera.powered, camera.captures, camera.last_target = True, camera.captures + 1, {"azimuth_deg": azimuth_deg, "elevation_deg": elevation_deg}
        self.state.eps.battery_wh -= 0.04; self.state.storage_used_mb += 4
        receipt = {"capture_id": f"SIM-CAM-{camera.captures:04d}", **camera.last_target}
        self.bus.publish("camera.capture", actor, **receipt); return receipt

    def handle_packet(self, raw: bytes, session_id: str = "default") -> bytes:
        packet = SpacePacket.parse(raw)
        if not packet.is_command: raise PacketError("spacecraft accepts command packets only")
        try: request = json.loads(packet.data)
        except Exception as exc: raise PacketError("command data must be JSON") from exc
        txid = str(request.get("txid", ""))
        if not txid: raise PacketError("missing transaction id")
        if packet.apid == APID_PING: body = {"txid": txid, "reply": "pong"}
        elif packet.apid == APID_STATUS: body = {"txid": txid, "status": self.telemetry()}
        elif packet.apid == APID_COUNTER_SYNC:
            ok, reason = self.sync_counter(session_id, int(request["counter"])); body = {"txid": txid, "accepted": ok, "reason": reason}
        elif packet.apid == APID_FLAG: body = {"txid": txid, "flag": self.request_flag(session_id, int(request["counter"]))}
        elif packet.apid == APID_CAMERA: body = {"txid": txid, "receipt": self.point_camera(float(request["azimuth_deg"]), float(request["elevation_deg"]), "packet")}
        else: raise PacketError(f"unsupported APID {packet.apid}")
        self.state.comms_frames += 1; self.bus.publish("packet.command", "comms", apid=packet.apid, txid=txid)
        return SpacePacket(APID_RESPONSE, packet.sequence_count, json.dumps(body, sort_keys=True).encode(), is_command=False).serialize()
