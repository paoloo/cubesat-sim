# Security and research-safety policy

## Supported use

CubeSec-Sim supports offline study of synthetic baseband signals and bounded
software orchestration. Every mission identity and payload must be fictional.

## Prohibited use

Do not connect this package to RF hardware, live services or operational
spacecraft. Do not add real coordinates, TLEs, callsigns, tuning frequencies,
credentials, target identifiers, uplink, transmission, interference, replay
against third parties, or command execution. The configuration validator blocks
common representations, but technical controls do not replace authorization.

## Reporting

Report vulnerabilities through the repository's private security-advisory form
before public disclosure. Do not include real mission data, credentials or
device identifiers in an issue.

## Data publication

Generated synthetic IQ is safe to publish only after the manifest is reviewed
to confirm that no locally added policy or payload introduced external data.
Publish hashes and software versions with every dataset release.
