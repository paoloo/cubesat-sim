# Standards and profile lock for 1.0.0

This release separates three kinds of claims: protocol-family implementation,
laboratory profile, and external conformance. Only the first two are claimed.

## Frozen profiles

- Space Packet primary header: CCSDS 133.0-B family field layout, version zero,
  11-bit APID, two sequence flags, 14-bit sequence count, and the normative
  `subsequent octets minus one` packet-data-length semantics. The test suite
  freezes an independently inspectable byte vector.
- Protected telemetry: `SIM-TM-AES256-GCM-v1`, a fixed teaching profile. Its
  fields are a 4-octet TM-inspired primary header, 2-octet SPI, 8-octet
  anti-replay counter, 2-octet plaintext length, AES-256-GCM ciphertext and
  16-octet tag, then CRC-16/CCITT-FALSE FECF. The 12-octet GCM nonce is
  `SPI || anti_replay || 0x0000`; all headers are authenticated data.
- AX.25: modulo-8 UI frame with variable 7-octet destination, source and APRS
  digipeater address chain, control `0x03`, PID `0xf0`, HDLC bit stuffing,
  NRZI, and CRC-16/X-25 FCS.
- AFSK: 1200 baud, 1200 Hz mark and 2200 Hz space, mono signed 16-bit PCM WAV.

`SIM-TM-AES256-GCM-v1` is not called CCSDS SDLS conformant. Formal conformance
remains blocked until an exact Blue Book edition, managed parameters, and
redistributable external vectors are selected and cross-validated.

## Orbital propagation

`sgp4` 2.24–2.x is the selected maintained propagator. When the optional orbit
extra is absent, the software uses a clearly reported two-body Kepler fallback;
fallback results are functional approximations and not SGP4 validation data.
