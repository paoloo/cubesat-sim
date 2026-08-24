# Simulation credibility and limitations

The intended use is comparison of software trajectories under controlled,
synthetic inputs. Credibility is supported by protocol known vectors, noiseless
round-trips, corruption rejection, deterministic replay, paired randomness,
parameter publication, configuration hashes and negative controls.
The audit command regenerates IQ from the frozen seed tree instead of merely
trusting stored hashes.

The artifact does not validate an antenna, LNA, oscillator, SDR driver, orbital
propagator, atmospheric model or real mission. The elevation, SNR and Doppler
profiles are smooth proxies rather than propagation predictions. Symbol timing
is aligned, and the receiver does not yet perform acquisition from an unknown
stream. The CCSDS-inspired profile omits several coding and synchronization
options and must not be described as conformance.

Accordingly, defensible claims concern repeatability, sensitivity to injected
impairments, policy coverage, failure localization and auditability. Claims about
in-orbit packet error rate, link budget or operational safety require independent
experimental evidence outside this artifact.
