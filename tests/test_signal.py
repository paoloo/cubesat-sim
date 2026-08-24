import unittest

import numpy as np
from cubesec_sim.channel import apply_channel, compensate_clock, derotate
from cubesec_sim.config import ChannelConfig, Protocol, SimulationConfig
from cubesec_sim.modem import demodulate_payload, modulate_payload
from cubesec_sim.policies import (
    BoundedSearchPolicy,
    DirectDecodeAblation,
    ScriptedBaseline,
)


class SignalTests(unittest.TestCase):
    def test_zero_impairment_roundtrip_both_protocols(self):
        for protocol in Protocol:
            with self.subTest(protocol=protocol):
                cfg = SimulationConfig(
                    protocol=protocol, channel=ChannelConfig(snr_db=100.0)
                )
                payload = b"SIM:0001:" + bytes(range(32))
                clean = modulate_payload(payload, cfg)
                impaired = apply_channel(clean, cfg.channel, np.random.default_rng(5))
                self.assertEqual(demodulate_payload(impaired, cfg), payload)

    def test_channel_is_deterministic(self):
        cfg = ChannelConfig(
            snr_db=5.0, cfo_cycles_per_sample=0.004, impulse_probability=0.001
        )
        signal = np.ones(1000, dtype=np.complex64)
        first = apply_channel(signal, cfg, np.random.default_rng(7))
        second = apply_channel(signal, cfg, np.random.default_rng(7))
        self.assertEqual(first.tobytes(), second.tobytes())

    def test_clock_error_is_nonzero_and_approximately_compensated(self):
        phase = np.linspace(0, 20 * np.pi, 8000)
        signal = np.exp(1j * phase).astype(np.complex64)
        cfg = ChannelConfig(snr_db=200.0, sample_clock_ppm=50.0)
        impaired = apply_channel(signal, cfg, np.random.default_rng(4))
        self.assertFalse(np.array_equal(signal, impaired))
        restored = compensate_clock(impaired, 50.0)
        self.assertLess(float(np.mean(np.abs(restored[16:-16] - signal[16:-16]))), 0.02)

    def test_manifest_baseline_corrects_nominal_frequency_offset(self):
        cfg = SimulationConfig(
            protocol=Protocol.CCSDS_BPSK,
            channel=ChannelConfig(
                snr_db=30.0,
                cfo_cycles_per_sample=0.004,
                doppler_cycles_per_sample=0.002,
            ),
        )
        payload = b"SIM:0001:" + bytes(range(32))
        clean = modulate_payload(payload, cfg)
        impaired = apply_channel(
            clean, cfg.channel, np.random.default_rng(8), pass_fraction=0.25
        )
        from cubesec_sim.geometry import doppler_at_fraction

        corrected = derotate(
            compensate_clock(impaired, 0.0), 0.004 + doppler_at_fraction(0.25, 0.002)
        )
        self.assertEqual(demodulate_payload(corrected, cfg), payload)

    def test_bpsk_phase_ambiguity_is_resolved_by_primary_policies(self):
        cfg = SimulationConfig(
            protocol=Protocol.CCSDS_BPSK,
            channel=ChannelConfig(snr_db=30.0, phase_offset_rad=np.pi),
        )
        payload = b"SIM:0002:" + bytes(range(32))
        impaired = apply_channel(
            modulate_payload(payload, cfg),
            cfg.channel,
            np.random.default_rng(12),
            pass_fraction=0.5,
        )
        self.assertEqual(
            ScriptedBaseline().decode(impaired, cfg, np.random.default_rng(1)).payload,
            payload,
        )
        self.assertEqual(
            BoundedSearchPolicy()
            .decode(impaired, cfg, np.random.default_rng(1))
            .payload,
            payload,
        )
        self.assertFalse(
            DirectDecodeAblation()
            .decode(impaired, cfg, np.random.default_rng(1))
            .success
        )

    def test_fractional_multipath_is_deterministic_and_nontrivial(self):
        signal = np.exp(1j * np.linspace(0, 30, 2000)).astype(np.complex64)
        cfg = ChannelConfig(
            snr_db=200.0, multipath_delay_samples=1.5, multipath_gain=0.35
        )
        first = apply_channel(signal, cfg, np.random.default_rng(22))
        second = apply_channel(signal, cfg, np.random.default_rng(22))
        self.assertEqual(first.tobytes(), second.tobytes())
        self.assertFalse(np.array_equal(first, signal))


if __name__ == "__main__":
    unittest.main()
