# Integrated CubeSat simulator

CubeSec-Sim 1.0 adds a local Software-in-the-Loop 3U reference mission. One
mission state is shared by OBC, scheduler, COMMS, EPS, ADCS, payload/camera,
storage, thermal behavior, FDIR mode, the dashboard and all scenario evidence.
A camera command therefore changes attitude, battery, storage and telemetry.

The deterministic virtual clock is the verification default. `--wall-clock`
is available for demonstrations. There is no RF backend, device access,
network listener, external endpoint, or operational spacecraft identifier.

Run the complete lab with:

```bash
cubesec-sim lab up
cubesec-sim verify --suite all --output artifacts/verification-001
```

Scenario 7 accepts WAV, OGG, or an auditable SatNOGS fixture directory. The
validated fixture is bundled for offline classroom use:

```bash
cubesec-sim verify --suite afsk \
  --afsk-capture fixtures/satnogs-14894580 \
  --output artifacts/afsk-classroom-001
```

New fixtures can also be acquired explicitly; verification remains offline:

```bash
cubesec-sim fixtures fetch-satnogs 14894580 \
  --output fixtures/satnogs-14894580
cubesec-sim verify --suite afsk \
  --afsk-capture fixtures/satnogs-14894580 \
  --output artifacts/afsk-real-001
```

The default remains the deterministic synthetic encoder fixture, generated in
memory for every run. It can also be materialized with `fixtures generate-afsk`.
OGG decoding
requires `ffmpeg`. SatNOGS raw demodulated frames are compared byte-for-byte
against recovered AX.25 frames after removal of the FCS that SatNOGS omits.

Each new output directory contains a manifest, environment, global event log,
per-scenario result and transcript, summary, and Markdown report. Existing
directories are never overwritten.
