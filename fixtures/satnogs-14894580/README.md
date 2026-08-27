# SatNOGS observation 14894580

Real passive AFSK1200/APRS classroom fixture acquired from SatNOGS Network.

- Observation: `14894580`
- Time: 2026-08-27 01:01:28–01:11:54 UTC
- Station: `Alx2`
- Observer: `m00f`
- Recorded frequency: 144.390 MHz
- Audio: mono OGG/Vorbis
- Reference frames: 29, without AX.25 FCS
- License: CC BY-SA 4.0
- Audio SHA-256:
  `227f71062aa94e3cd21de5c3f6632d9261998473f51ebb0cd83e73a4425ae31b`

Attribution: “SatNOGS observation 14894580; station Alx2; observer m00f”.
The complete API response, source URLs, sizes and hashes are frozen in
`manifest.json`.

Although the recording belongs to an observation scheduled for NORAD 40908,
144.390 MHz and the decoded callsigns identify terrestrial APRS traffic. Use it
to teach real noisy AFSK/AX.25 acquisition, not as evidence that the packets
originated from a satellite.

Run it with:

```bash
cubesec-sim verify --suite afsk \
  --afsk-capture fixtures/satnogs-14894580 \
  --output artifacts/afsk-classroom-001
```

