# Third-party notices and influences

CubeSec-Sim uses NumPy (BSD 3-Clause) and cryptography (Apache-2.0 OR BSD-3-Clause)
as normal package dependencies; neither is vendored. The optional orbital extra
uses sgp4 (MIT) from its normal package distribution.

SatNOGS observation data acquired by the optional fixture command are licensed
CC BY-SA 4.0. Each fixture manifest preserves the observation ID, station,
observer, source URLs, license and checksums. Data are not bundled in the source
distribution. `satnogs-decoders` (AGPL-3.0) and `gr-satnogs` (GPL-3.0+) are used
as documented external references only; their source is not copied or linked.

The following public projects informed design choices but no source code from
them is copied or included:

- FloripaSat and SpaceLab-UFSC firmware/documentation — commonly GPL-3.0 for
  firmware and CC-BY-SA-4.0 for documentation;
- gr-satellites — GPL-3.0;
- gr-leo — consult its upstream repository for the applicable license;
- gr-ccsds — GPL-3.0.

The implementations in `src/cubesec_sim` were written independently for this
artifact. AX.25 and CCSDS are named to identify public protocol families. The
CCSDS path is deliberately described as “CCSDS-inspired” and is not a standards
conformance implementation.

Before release, archive the exact upstream pages and standards consulted in the
dissertation bibliography. Do not copy upstream test vectors unless their
redistribution terms are recorded here.
