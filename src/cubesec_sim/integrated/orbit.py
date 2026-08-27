"""TLE propagation, observer geometry, pass finding and rotor dynamics."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import math
from typing import Callable

import numpy as np

EARTH_MU_KM3_S2 = 398600.4418
EARTH_RADIUS_KM = 6378.137
EARTH_FLATTENING = 1 / 298.257223563
LIGHT_SPEED_M_S = 299792458.0


def tle_checksum(line: str) -> int:
    return sum(int(c) if c.isdigit() else 1 if c == "-" else 0 for c in line[:68]) % 10


@dataclass(frozen=True)
class TLE:
    line1: str
    line2: str
    epoch: datetime
    inclination_deg: float
    raan_deg: float
    eccentricity: float
    argument_perigee_deg: float
    mean_anomaly_deg: float
    mean_motion_rev_day: float

    @classmethod
    def parse(cls, line1: str, line2: str) -> "TLE":
        if len(line1) != 69 or len(line2) != 69 or not line1.startswith("1 ") or not line2.startswith("2 "):
            raise ValueError("TLE lines must be 69-character line 1/2 records")
        if tle_checksum(line1) != int(line1[68]) or tle_checksum(line2) != int(line2[68]):
            raise ValueError("invalid TLE checksum")
        if line1[2:7] != line2[2:7]: raise ValueError("TLE catalog identifiers differ")
        year2, day = int(line1[18:20]), float(line1[20:32])
        year = 2000 + year2 if year2 < 57 else 1900 + year2
        epoch = datetime(year, 1, 1, tzinfo=timezone.utc) + timedelta(days=day - 1)
        try:
            return cls(line1, line2, epoch, float(line2[8:16]), float(line2[17:25]), float("0." + line2[26:33].strip()), float(line2[34:42]), float(line2[43:51]), float(line2[52:63]))
        except ValueError as exc: raise ValueError("invalid numeric TLE field") from exc


@dataclass(frozen=True)
class GroundStation:
    latitude_deg: float
    longitude_deg: float
    altitude_m: float

    def __post_init__(self) -> None:
        if not -90 <= self.latitude_deg <= 90 or not -180 <= self.longitude_deg <= 180 or not -500 <= self.altitude_m <= 10000:
            raise ValueError("ground station coordinate outside supported domain")


@dataclass(frozen=True)
class LookAngle:
    time: datetime
    azimuth_deg: float
    elevation_deg: float
    range_km: float
    range_rate_km_s: float
    doppler_hz: float


@dataclass(frozen=True)
class Pass:
    aos: datetime
    tca: datetime
    los: datetime
    max_elevation_deg: float
    duration_s: float


def _gmst(dt: datetime) -> float:
    unix_days = dt.timestamp() / 86400
    jd = 2440587.5 + unix_days
    t = (jd - 2451545.0) / 36525
    deg = 280.46061837 + 360.98564736629 * (jd - 2451545) + 0.000387933 * t * t
    return math.radians(deg % 360)


class Propagator:
    def __init__(self, tle: TLE, *, prefer_sgp4: bool = True):
        self.tle, self.backend, self._sat = tle, "kepler-fallback", None
        if prefer_sgp4:
            try:
                from sgp4.api import Satrec
                self._sat, self.backend = Satrec.twoline2rv(tle.line1, tle.line2), "sgp4"
            except ImportError:
                pass

    def eci_km(self, when: datetime) -> np.ndarray:
        when = when.astimezone(timezone.utc)
        if self._sat is not None:
            from sgp4.api import jday
            sec = when.second + when.microsecond / 1e6
            jd, fr = jday(when.year, when.month, when.day, when.hour, when.minute, sec)
            error, position, _ = self._sat.sgp4(jd, fr)
            if error: raise RuntimeError(f"SGP4 propagation error {error}")
            return np.asarray(position, dtype=float)
        t = (when - self.tle.epoch).total_seconds()
        n = self.tle.mean_motion_rev_day * 2 * math.pi / 86400
        a = (EARTH_MU_KM3_S2 / n**2) ** (1 / 3)
        mean = math.radians(self.tle.mean_anomaly_deg) + n * t
        ecc, eanom = self.tle.eccentricity, mean
        for _ in range(8): eanom -= (eanom - ecc * math.sin(eanom) - mean) / (1 - ecc * math.cos(eanom))
        x, y = a * (math.cos(eanom) - ecc), a * math.sqrt(1 - ecc * ecc) * math.sin(eanom)
        raan, inc, arg = map(math.radians, (self.tle.raan_deg, self.tle.inclination_deg, self.tle.argument_perigee_deg))
        rotation = np.array([
            [math.cos(raan)*math.cos(arg)-math.sin(raan)*math.sin(arg)*math.cos(inc), -math.cos(raan)*math.sin(arg)-math.sin(raan)*math.cos(arg)*math.cos(inc), math.sin(raan)*math.sin(inc)],
            [math.sin(raan)*math.cos(arg)+math.cos(raan)*math.sin(arg)*math.cos(inc), -math.sin(raan)*math.sin(arg)+math.cos(raan)*math.cos(arg)*math.cos(inc), -math.cos(raan)*math.sin(inc)],
            [math.sin(arg)*math.sin(inc), math.cos(arg)*math.sin(inc), math.cos(inc)],
        ])
        return rotation @ np.array([x, y, 0.0])

    def look(self, station: GroundStation, when: datetime, carrier_hz: float = 437_500_000.0) -> LookAngle:
        def range_at(t: datetime) -> tuple[float, float, float]:
            theta = _gmst(t); c, s = math.cos(theta), math.sin(theta)
            eci = self.eci_km(t); ecef = np.array([c*eci[0]+s*eci[1], -s*eci[0]+c*eci[1], eci[2]])
            lat, lon, alt = math.radians(station.latitude_deg), math.radians(station.longitude_deg), station.altitude_m / 1000
            e2 = EARTH_FLATTENING * (2 - EARTH_FLATTENING); n = EARTH_RADIUS_KM / math.sqrt(1 - e2 * math.sin(lat)**2)
            site = np.array([(n+alt)*math.cos(lat)*math.cos(lon), (n+alt)*math.cos(lat)*math.sin(lon), (n*(1-e2)+alt)*math.sin(lat)])
            d = ecef - site
            east = -math.sin(lon)*d[0] + math.cos(lon)*d[1]
            north = -math.sin(lat)*math.cos(lon)*d[0] - math.sin(lat)*math.sin(lon)*d[1] + math.cos(lat)*d[2]
            up = math.cos(lat)*math.cos(lon)*d[0] + math.cos(lat)*math.sin(lon)*d[1] + math.sin(lat)*d[2]
            rng = float(np.linalg.norm(d)); az = math.degrees(math.atan2(east, north)) % 360; el = math.degrees(math.asin(up / rng))
            return rng, az, el
        rng, az, el = range_at(when)
        rate = (range_at(when + timedelta(seconds=.5))[0] - range_at(when - timedelta(seconds=.5))[0])
        return LookAngle(when, az, el, rng, rate, -carrier_hz * rate * 1000 / LIGHT_SPEED_M_S)

    def passes(self, station: GroundStation, start: datetime, end: datetime, mask_deg: float = 5, step_s: float = 30) -> list[Pass]:
        if end <= start or not 0 < step_s <= 300 or not -5 <= mask_deg < 90: raise ValueError("invalid pass search interval")
        def f(t: datetime) -> float: return self.look(station, t).elevation_deg - mask_deg
        def root(a: datetime, b: datetime) -> datetime:
            fa = f(a)
            for _ in range(35):
                m = a + (b-a)/2; fm = f(m)
                if (fa >= 0) == (fm >= 0): a, fa = m, fm
                else: b = m
            return a + (b-a)/2
        times, t = [start], start
        while t < end: t = min(end, t + timedelta(seconds=step_s)); times.append(t)
        result: list[Pass] = []; aos = start if f(start) >= 0 else None
        for left, right in zip(times, times[1:]):
            fl, fr = f(left), f(right)
            if aos is None and fl < 0 <= fr: aos = root(left, right)
            if aos is not None and fl >= 0 > fr:
                los = root(left, right)
                lo, hi = aos, los
                for _ in range(35):
                    third = (hi-lo)/3; m1, m2 = lo+third, hi-third
                    if f(m1) < f(m2): lo = m1
                    else: hi = m2
                tca = lo + (hi-lo)/2; peak = self.look(station, tca).elevation_deg
                result.append(Pass(aos, tca, los, peak, (los-aos).total_seconds())); aos = None
        return result


@dataclass
class Antenna:
    azimuth_deg: float = 0.0
    elevation_deg: float = 0.0
    max_speed_deg_s: float = 20.0
    max_acceleration_deg_s2: float = 40.0
    azimuth_velocity_deg_s: float = 0.0
    elevation_velocity_deg_s: float = 0.0

    @staticmethod
    def _az_error(target: float, actual: float) -> float: return (target - actual + 180) % 360 - 180

    def update(self, target_azimuth_deg: float, target_elevation_deg: float, dt_s: float) -> float:
        if dt_s <= 0: raise ValueError("rotor dt must be positive")
        errors = (self._az_error(target_azimuth_deg, self.azimuth_deg), target_elevation_deg-self.elevation_deg)
        velocities = [self.azimuth_velocity_deg_s, self.elevation_velocity_deg_s]
        for i, error in enumerate(errors):
            desired = max(-self.max_speed_deg_s, min(self.max_speed_deg_s, error/dt_s))
            delta = max(-self.max_acceleration_deg_s2*dt_s, min(self.max_acceleration_deg_s2*dt_s, desired-velocities[i]))
            velocities[i] += delta
        self.azimuth_velocity_deg_s, self.elevation_velocity_deg_s = velocities
        self.azimuth_deg = (self.azimuth_deg + velocities[0]*dt_s) % 360
        self.elevation_deg = max(0, min(90, self.elevation_deg + velocities[1]*dt_s))
        return math.hypot(self._az_error(target_azimuth_deg, self.azimuth_deg), target_elevation_deg-self.elevation_deg)

