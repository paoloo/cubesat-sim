# CubeSec-Sim

[![Release](https://img.shields.io/github/v/release/paoloo/cubesat-sim)](https://github.com/paoloo/cubesat-sim/releases/tag/v0.2.0)

CubeSec-Sim is a fully offline, synthetic CubeSat communications and
tool-orchestration simulator. It was built as a reproducible research artifact:
it does not tune a radio, transmit RF, control a physical rotor, or contact an
operational spacecraft. Verification is offline; only the optional fixture
acquisition command performs read-only access to the public SatNOGS archive.

Version 1.0 evolves the original link study into an integrated 3U Software-in-
the-Loop mission model. Seven end-to-end scenarios share the same spacecraft
state: TLE visibility, Space Packets, stateful counters, protected telemetry,
antenna tracking, a local dashboard security lab, and passive AFSK1200 capture
decoding. See [`docs/integrated-simulator.md`](docs/integrated-simulator.md).

The artifact generates AX.25/AFSK and a bounded CCSDS-inspired/BPSK profile
with rate-1/2, constraint-length-7 convolutional coding and hard Viterbi decoding,
passes immutable complex64 IQ through a time-varying channel, and evaluates two
receiver-control policies on the exact same latent realization. It records exact
denominators, hashes and paired statistical comparisons.

## Scope and claim

This is a **simulation study**, not evidence of in-orbit performance and not a
CCSDS conformance suite. The scripted policy reads the injected impairment
manifest and therefore represents an idealized upper bound. The bounded-search
policy sees IQ but not the injected channel values. See
[`docs/credibility.md`](docs/credibility.md).

## Quick start

Python 3.11 or newer is required. Installation brings NumPy and cryptography;
`ffmpeg` is additionally required to decode the bundled OGG recording.

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e .
python -m unittest discover -s tests -v
cubesec-sim init-config simulation.json
cubesec-sim run --config simulation.json --profile quick --output artifacts/quick
cubesec-sim lab up
cubesec-sim verify --suite all --output artifacts/verification-001
```

## Offline classroom commands

The repository includes everything needed for repeated offline exercises.
Use the bundled passive recording and its 29 SatNOGS reference frames:

```bash
cubesec-sim verify --suite afsk \
  --afsk-capture fixtures/satnogs-14894580 \
  --output artifacts/afsk-real-001
```

Generate and decode a deterministic synthetic signal entirely in memory:

```bash
cubesec-sim verify --suite afsk \
  --output artifacts/afsk-synthetic-001
```

Materialize a reusable synthetic WAV and its hash manifest:

```bash
cubesec-sim fixtures generate-afsk \
  --payload CLASSROOM-TEST \
  --output /tmp/simul-generated-classroom

cubesec-sim verify --suite afsk \
  --afsk-capture /tmp/simul-generated-classroom \
  --output artifacts/afsk-generated-001
```

Every output directory must be new; runners deliberately refuse overwrites.
See [`docs/data-provenance.md`](docs/data-provenance.md) for the real fixture's
attribution and satellite-origin caveat.

The `smoke` profile contains one design cell and one paired replication. The
`quick` profile has 16 cells and defaults to three replications. `controls`
contains protocol-specific high-SNR positive and -20 dB negative controls;
`stress` isolates nine nominal/impairment conditions. The `full`
profile has 768 cells and defaults to 30 replications: 23,040 paired runs and
46,080 primary-policy records, with eight frames per run by default. Enabling
the diagnostic ablation produces 69,120 records.

Use a new output directory for every campaign. The runner refuses to overwrite
an existing directory. Generated IQ and JSONL files are ignored by Git and can
be deposited as a separate versioned dataset.

## Reproducibility

- NumPy `SeedSequence` and `PCG64` derive stable, separated channel and policy
  streams from the master seed, cell hash and replication index.
- Baseline and candidate receive byte-identical IQ for every `pair_id`.
- `campaign.json` freezes the design and environment.
- `source_sha256` binds every package module used by the campaign.
- `runs.jsonl` is append-only during execution and flushed to disk per record.
- SHA-256 binds IQ, configurations and manifests to results.
- `summary.json` reports Wilson intervals, exact paired McNemar and a paired
  bootstrap difference, plus descriptive factor strata and failure counts.
- `cubesec-sim audit artifacts/quick` regenerates every paired IQ realization
  from its seed and verifies manifest, configuration, stored-IQ and pair hashes.
- `cubesec-sim report artifacts/quick` emits hashed Markdown, CSV and LaTeX
  tables ready for inspection and dissertation integration.
- `cubesec-sim quality artifacts/controls` applies the frozen integrity and
  control gates without selecting for a favorable policy comparison.

Use `--ablations` to add a direct-decode policy with all correction/search tools
removed. It is a diagnostic secondary comparison, not part of the primary pair.

## Safety boundary

Configurations reject device paths, URLs, TLE lines, coordinates, RF tuning
frequencies, real callsigns and non-synthetic transmission/uplink/command,
jamming or spoofing operations. The package contains no radio-device backend.
See [`SECURITY.md`](SECURITY.md).

The exact field definitions and technical sources are listed in
[`docs/data_dictionary.md`](docs/data_dictionary.md) and
[`docs/references.md`](docs/references.md).

## Influences and clean-room status

Public FloripaSat/SpaceLab documentation, gr-satellites and gr-leo informed the
choice of test profiles and impairments. Their source code is not vendored or
copied. The protocol primitives here are independent, limited implementations;
see [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

## Citation

Use [`CITATION.cff`](CITATION.cff) and the tagged
[`v0.2.0` release](https://github.com/paoloo/cubesat-sim/releases/tag/v0.2.0).
An archival DOI will be added to the citation metadata if one is assigned.
