# Contributing

Contributions must preserve the offline synthetic boundary. Open an issue before
adding a protocol or impairment and describe its source, license, intended claim,
validation oracle and computational cost.

Run before submitting a change:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python -m cubesec_sim run --profile smoke --output artifacts/smoke
```

Never commit generated IQ, campaign JSONL, credentials, device identifiers,
coordinates, TLEs, real callsigns or mission payloads. New randomness must be
derived from the existing seed tree and must not break pairing.

