# Changelog

All notable changes are documented here following semantic versioning.

## 0.2.0 — 2026-08-24

- Corrected CCSDS legacy randomizer against the normative prefix and added
  second-symbol inversion to the convolutional code.
- Mapped frames to distinct instants of a spherical-Earth synthetic pass.
- Made sample-clock error nonzero without integer-length rounding.
- Vectorized hard Viterbi decoding.
- Added positive/negative controls, one-factor stress diagnostics and ablation.
- Added order-independent policy RNG streams and stronger regenerative audits.
- Added hashed Markdown, CSV, per-cell and LaTeX report exports.

## 0.1.0 — 2026-08-24

- Initial offline synthetic simulator.
- AX.25 UI/HDLC/AFSK and bounded CCSDS-inspired TM/BPSK profiles.
- Time-varying pass geometry, relative path loss, Doppler, AWGN, clock error,
  multipath, erasures, impulsive noise and clipping.
- Paired deterministic and bounded-search receiver policies.
- Frozen factorial profiles, hashes, JSONL provenance and paired statistics.
- Safety validation, unit tests and publication documentation.
