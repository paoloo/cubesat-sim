# Threat model and containment

The protected assets are synthetic security keys, flags, mission state and
verification evidence. The modeled adversary can submit malformed packets,
replay protected frames and alter a dashboard claim. The only intentionally
vulnerable target is the in-process `Dashboard(profile="vulnerable")` object
created by the runner.

The simulator has no RF transmission path, SDR/device adapter or network listener.
The only network operation is the explicit `fixtures fetch-satnogs` acquisition
command. It performs read-only HTTPS GETs against a fixed official API and an
allowlist of SatNOGS storage hosts; normal verification never contacts them.
The dashboard exploit helper accepts only a token
created by the local object and never accepts a host or URL. A supplied AFSK WAV
is read passively. Existing 0.2 configuration validation continues rejecting
TLEs, coordinates, external callsigns and transmission operations in the legacy
campaign interface; 1.0 orbital fixtures live in the isolated integrated API.

Synthetic keys are deterministically derived for repeatable tests and must not
be used outside this laboratory. Evidence stores flag hashes, never lab keys.
