# Third-party notices and influences

CubeSec-Sim has one runtime dependency, NumPy, distributed under the BSD
3-Clause license. NumPy is installed from its normal package distribution and is
not vendored here.

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

