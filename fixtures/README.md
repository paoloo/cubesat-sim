# Classroom fixtures

This directory contains immutable inputs for the integrated laboratory.

- `satnogs-14894580/`: real passive AFSK1200/APRS audio plus 29 external raw
  frames. See its own README and manifest for provenance and the satellite-origin
  caveat.
- Synthetic fixtures are normally generated in memory. To materialize one:

```bash
cubesec-sim fixtures generate-afsk \
  --payload SIMUL-AFSK1200-CLASSROOM \
  --output /tmp/simul-afsk-synthetic
```

Do not modify a fixture used in a published campaign. Derive a new directory,
record the transformation and preserve both hashes.

