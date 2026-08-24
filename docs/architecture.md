# Architecture

The simulator separates five layers:

1. `ax25`, `hdlc` and `ccsds` create synthetic frames.
2. `modem` maps bits to complex baseband samples.
3. `geometry` and `channel` inject controlled time-varying impairments.
4. `policies` select deterministic correction and decoding tools.
5. `campaign` pairs policies, preserves provenance and calls `stats`.

The channel is generated once per `pair_id`. Policies receive copies of that
same array. Randomness used by a policy cannot change AWGN, erasures or payloads.

## Signal chain

For AFSK, AX.25 UI bytes receive CRC-16/X-25, HDLC bit stuffing, flags and NRZI.
Continuous-phase binary FSK uses a mark at zero after abstract downconversion and
a normalized space-tone separation. For the CCSDS-inspired profile, a synthetic
space packet and small TM header receive CRC-16/CCITT-FALSE, an additive PN
randomizer, rate-1/2 constraint-length-7 convolutional coding with `(171,133)`
octal generators (including the recommended second-symbol inversion) and the
attached sync marker `1ACFFC1D`, then BPSK. The legacy 255-bit randomizer is
tested against the published CCSDS prefix `ff480ec09a0d70bc8e`.

The channel treats every frame as a short observation at a recorded instant of
the synthetic pass. Slant range, local SNR and Doppler therefore change between
frames rather than being unrealistically compressed into one frame. It can also
apply fractional-delay two-ray multipath, sample-clock error, constant frequency
offset, 180-degree carrier ambiguity, gain, burst erasures, impulsive noise and
clipping. No absolute RF carrier is represented.

## Policy interface

`ScriptedBaseline` is an ideal upper bound with access to the injected channel
manifest. `BoundedSearchPolicy` is a transparent agent-like controller that sees
only IQ and calls a fixed frequency-search/decode sequence. A future LLM policy
must implement the same `ReceiverPolicy` contract and must be evaluated on frozen
IQ; it must not be allowed to regenerate a channel after seeing an outcome.
