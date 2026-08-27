"""In-process, local-only vulnerable and patched dashboard profiles."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
from typing import Any

from .spacecraft import Spacecraft


@dataclass(frozen=True)
class Principal:
    username: str
    role: str


class Dashboard:
    """Minimal IDOR/unsigned-claim teaching target without a network listener."""
    def __init__(self, spacecraft: Spacecraft, *, profile: str, secret: bytes):
        if profile not in {"vulnerable", "patched"}: raise ValueError("unknown dashboard profile")
        self.spacecraft, self.profile, self.secret = spacecraft, profile, secret
        self.users = {"viewer": Principal("viewer", "viewer"), "operator": Principal("operator", "operator")}
        self.audit: list[dict[str, Any]] = []

    def login(self, username: str) -> str:
        principal = self.users[username]
        claim = json.dumps({"sub": principal.username, "role": principal.role}, sort_keys=True, separators=(",", ":")).encode()
        signature = hmac.new(self.secret, claim, hashlib.sha256).hexdigest()
        return claim.hex() + "." + signature

    def _principal(self, token: str) -> Principal:
        try: claim_hex, signature = token.split("."); claim = bytes.fromhex(claim_hex); data = json.loads(claim)
        except Exception as exc: raise PermissionError("invalid dashboard token") from exc
        if self.profile == "patched" and not hmac.compare_digest(signature, hmac.new(self.secret, claim, hashlib.sha256).hexdigest()):
            raise PermissionError("invalid dashboard signature")
        if data.get("sub") not in self.users or data.get("role") not in {"viewer", "operator"}: raise PermissionError("invalid dashboard claim")
        return Principal(data["sub"], data["role"])

    def alter_claim_for_lab(self, token: str, role: str) -> str:
        claim_hex, signature = token.split("."); data = json.loads(bytes.fromhex(claim_hex)); data["role"] = role
        claim = json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
        return claim.hex() + "." + signature

    def camera_point(self, token: str, azimuth_deg: float, elevation_deg: float) -> dict[str, Any]:
        principal = self._principal(token)
        allowed = principal.role == "operator"
        record = {"identity": principal.username, "claimed_role": principal.role, "action": "camera.point", "allowed": allowed}
        self.audit.append(record); self.spacecraft.bus.publish("dashboard.authorization", "dashboard", **record)
        if not allowed: raise PermissionError("operator role required")
        return self.spacecraft.point_camera(azimuth_deg, elevation_deg, f"dashboard:{principal.username}")

