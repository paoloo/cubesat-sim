import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from cubesec_sim.integrated.core import EventBus, VirtualClock
from cubesec_sim.integrated.dashboard import Dashboard
from cubesec_sim.integrated.orbit import GroundStation, Propagator
from cubesec_sim.integrated.protocols import AuthenticationError, FrameError, PacketError, ReplayError, SecurityAssociation, SpacePacket, crc16_ccitt_false
from cubesec_sim.ax25 import encode_address
from cubesec_sim.hdlc import append_fcs, bit_stuff, bytes_to_bits, nrzi_encode
from cubesec_sim.integrated.radio import decode_afsk, generate_synthetic_fixture, synthesize_afsk
from cubesec_sim.integrated.runner import verify
from cubesec_sim.integrated.satnogs import _validated_data_url
from cubesec_sim.integrated.scenarios import reference_tle
from cubesec_sim.integrated.spacecraft import Spacecraft


class IntegratedProtocolTests(unittest.TestCase):
    def test_space_packet_frozen_vector_and_length(self):
        packet = SpacePacket(1, 7, b"abc")
        self.assertEqual(packet.serialize().hex(), "1001c0070002616263")
        self.assertEqual(SpacePacket.parse(packet.serialize()), packet)
        with self.assertRaises(PacketError):
            SpacePacket.parse(packet.serialize()[:-1])

    def test_protected_tm_detects_layers_and_replay(self):
        sa = SecurityAssociation(4, b"x" * 32)
        raw = sa.encode(b"payload", anti_replay=9)
        self.assertEqual(sa.decode(raw).payload, b"payload")
        with self.assertRaises(ReplayError):
            sa.decode(raw)
        bad = bytearray(raw); bad[-1] ^= 1
        with self.assertRaises(FrameError):
            sa.decode(bytes(bad), enforce_replay=False)
        bad = bytearray(raw); bad[18] ^= 1; bad[-2:] = crc16_ccitt_false(bad[:-2]).to_bytes(2, "big")
        with self.assertRaises(AuthenticationError):
            sa.decode(bytes(bad), enforce_replay=False)


class IntegratedMissionTests(unittest.TestCase):
    def setUp(self):
        self.clock = VirtualClock(); self.bus = EventBus(self.clock)
        self.spacecraft = Spacecraft(self.clock, self.bus, "run", 7)

    def test_subsystems_share_camera_effects(self):
        before_energy = self.spacecraft.state.eps.battery_wh
        receipt = self.spacecraft.point_camera(10, 20, "test")
        self.assertEqual(receipt["capture_id"], "SIM-CAM-0001")
        self.assertLess(self.spacecraft.state.eps.battery_wh, before_energy)
        self.assertEqual(self.spacecraft.state.storage_used_mb, 36)
        self.assertEqual(self.spacecraft.state.adcs.mode, "target")

    def test_stateful_replay_and_isolation(self):
        one = self.spacecraft.session("one"); two = self.spacecraft.session("two")
        self.assertIsNot(one, two)
        accepted = one.expected_counter
        self.assertTrue(self.spacecraft.sync_counter("one", accepted)[0])
        self.assertEqual(self.spacecraft.sync_counter("one", accepted), (False, "replay"))

    def test_watchdog_resets_sessions_but_retains_mission_state(self):
        self.spacecraft.session("one")
        energy = self.spacecraft.state.eps.battery_wh
        self.spacecraft.tick(31)
        self.assertEqual(self.spacecraft.state.watchdog_resets, 1)
        self.assertEqual(self.spacecraft.sessions, {})
        self.assertGreaterEqual(self.spacecraft.state.eps.battery_wh, energy)

    def test_dashboard_vulnerability_and_patch(self):
        vulnerable = Dashboard(self.spacecraft, profile="vulnerable", secret=b"secret")
        forged = vulnerable.alter_claim_for_lab(vulnerable.login("viewer"), "operator")
        vulnerable.camera_point(forged, 10, 10)
        patched = Dashboard(self.spacecraft, profile="patched", secret=b"secret")
        with self.assertRaises(PermissionError):
            patched.camera_point(patched.alter_claim_for_lab(patched.login("viewer"), "operator"), 10, 10)


class IntegratedPhysicalTests(unittest.TestCase):
    def test_tle_pass_geometry(self):
        prop = Propagator(reference_tle(), prefer_sgp4=False)
        station = GroundStation(-3.7319, -38.5267, 20)
        end = reference_tle().epoch.replace(hour=23, minute=59)
        passes = prop.passes(station, reference_tle().epoch, end)
        self.assertTrue(passes)
        self.assertTrue(all(p.aos < p.tca < p.los for p in passes))

    def test_afsk_acquires_arbitrary_offset_and_rejects_noise(self):
        frames = decode_afsk(synthesize_afsk(b"hello", leading_samples=17), 9600)
        self.assertEqual([f.payload for f in frames], [b"hello"])
        self.assertEqual(decode_afsk(np.zeros(1000), 9600), [])

    def test_afsk_accepts_aprs_digipeater_address_chain(self):
        from cubesec_sim.ax25 import FLAG
        body = encode_address("SIMGS") + encode_address("SIM001") + encode_address("SIMR1", last=True) + b"\x03\xf0aprs"
        bits = np.concatenate((FLAG, bit_stuff(bytes_to_bits(append_fcs(body))), FLAG))
        levels = nrzi_encode(np.concatenate((FLAG, FLAG, bits, FLAG))); sps = 8
        tones = np.where(np.repeat(levels, sps) == 1, 1200.0, 2200.0)
        samples = np.concatenate((np.zeros(11), .75*np.sin(np.cumsum(2*np.pi*tones/9600))))
        frames = decode_afsk(samples, 9600)
        self.assertEqual(frames[0].repeaters, ("SIMR1",))
        self.assertEqual(frames[0].payload, b"aprs")


class IntegratedRunnerTests(unittest.TestCase):
    def test_all_scenarios_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "verification"
            result = verify(output)
            self.assertTrue(result["passed"], result)
            self.assertEqual(result["scenarios_passed"], 7)
            self.assertTrue((output / "events.jsonl").exists())
            with self.assertRaises(FileExistsError):
                verify(output)
            manifest = json.loads((output / "manifest.json").read_text())
            self.assertTrue(manifest["offline_only"])

    def test_materialized_synthetic_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture, output = Path(tmp)/"fixture", Path(tmp)/"result"
            generate_synthetic_fixture(fixture, b"materialized")
            result = verify(output, suite="afsk", afsk_capture=fixture)
            self.assertTrue(result["passed"])

    def test_satnogs_fixture_url_is_strictly_allowlisted(self):
        valid = "https://network-satnogs.freetls.fastly.net/media/data_obs/2026/8/27/audio.ogg"
        self.assertEqual(_validated_data_url(valid), valid)
        with self.assertRaises(ValueError): _validated_data_url("https://example.org/audio.ogg")


if __name__ == "__main__":
    unittest.main()
