import unittest

import numpy as np
from cubesec_sim.ax25 import decode_ui, encode_ui
from cubesec_sim.ccsds import (
    convolutional_encode,
    decode_tm,
    encode_tm,
    randomizer,
    viterbi_decode,
)
from cubesec_sim.hdlc import bit_stuff, bit_unstuff, crc16_x25, nrzi_decode, nrzi_encode


class ProtocolTests(unittest.TestCase):
    def test_crc_x25_known_vector(self):
        self.assertEqual(crc16_x25(b"123456789"), 0x906E)

    def test_stuffing_and_nrzi_roundtrip(self):
        bits = np.array([1, 1, 1, 1, 1, 0, 1, 0] * 8, dtype=np.uint8)
        self.assertTrue(np.array_equal(bit_unstuff(bit_stuff(bits)), bits))
        self.assertTrue(np.array_equal(nrzi_decode(nrzi_encode(bits)), bits))

    def test_ax25_roundtrip_and_corruption(self):
        payload = b"SIM synthetic telemetry"
        encoded = encode_ui(payload)
        self.assertEqual(decode_ui(encoded)["payload"], payload)
        damaged = encoded.copy()
        damaged[len(damaged) // 2] ^= 1
        with self.assertRaises(ValueError):
            decode_ui(damaged)

    def test_ccsds_roundtrip_and_corruption(self):
        payload = b"SIM synthetic space packet"
        encoded = encode_tm(payload)
        self.assertEqual(decode_tm(encoded), payload)
        damaged = encoded.copy()
        damaged[-80:-20] ^= 1
        with self.assertRaises(ValueError):
            decode_tm(damaged)

    def test_convolutional_code_roundtrip_and_single_error_correction(self):
        bits = np.array([0, 1, 1, 0, 1, 0, 0, 1] * 4, dtype=np.uint8)
        coded = convolutional_encode(bits)
        coded[17] ^= 1
        self.assertTrue(np.array_equal(viterbi_decode(coded), bits))

    def test_ccsds_legacy_randomizer_normative_prefix(self):
        self.assertEqual(randomizer(9), bytes.fromhex("ff480ec09a0d70bc8e"))


if __name__ == "__main__":
    unittest.main()
