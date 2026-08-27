# Data and software provenance

Version 1.0.0 evolves the complete Git history of CubeSec-Sim 0.2.0. Its frozen
base is tag `v0.2.0`, commit
`fffbc40953baafd2f20497b350aa000b8047ba47`. Integrated verification manifests
record this base and hash every Python source file in the current tree.

The built-in TLE is a synthetic catalog entry (`99990`) created for the project.
It is not a historical observation. The default AFSK signal is generated from a
synthetic AX.25 frame and is labeled accordingly in evidence.

The validated real-signal teaching fixture is SatNOGS observation `14894580`,
station `Alx2`, observer `m00f`, licensed CC BY-SA 4.0. Its OGG SHA-256 is
`227f71062aa94e3cd21de5c3f6632d9261998473f51ebb0cd83e73a4425ae31b`.
The acquisition command records the API response, source URLs, attribution,
license, sizes and individual SHA-256 values for the audio and 29 reference
frames. Our receiver recovers 20 valid frames and 16 match SatNOGS references.

Important scope note: although this recording is attached to a SatNOGS
observation scheduled for NORAD 40908, its recorded frequency is 144.390 MHz and
the decoded callsigns are terrestrial APRS stations. It validates a real,
passive, noisy AFSK1200/AX.25 acquisition chain, but it must not be presented as
proof that the recovered packets originated from a spacecraft. A publishable
satellite-origin fixture remains a separate provenance selection task.

No third-party source is vendored. Runtime dependency licenses and upstream
roles are listed in `THIRD_PARTY_NOTICES.md`.
