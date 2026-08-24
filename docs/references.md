# Technical references

The simulator is a clean-room research implementation informed by public
standards and open-source project documentation. These references define the
intended conventions; the limitations in `credibility.md` take precedence over
any implication of formal conformance.

- TAPR. *AX.25 Link Access Protocol for Amateur Packet Radio*, version 2.2.
  <https://www.tapr.org/pdf/AX25.2.2.pdf>
- CCSDS. *TM Synchronization and Channel Coding*, CCSDS 131.0-B-5, September
  2023. <https://ccsds.org/Pubs/131x0b5.pdf>
- CCSDS. *TM Space Data Link Protocol*, CCSDS 132.0-B series. Active
  publications index: <https://ccsds.org/publications/allpubs/>
- JPL Deep Space Network. *Telemetry System, Data Decoding*, 810-005 208 Rev. C.
  <https://deepspace.jpl.nasa.gov/dsndocs/810-005/208/208C.pdf>
- NASA. *Standard for Models and Simulations*, NASA-STD-7009B.
  <https://standards.nasa.gov/standard/nasa/nasa-std-7009>
- FloripaSat/SpaceLab-UFSC public repositories, used for architectural context
  only: <https://github.com/spacelab-ufsc/spacelab>
- gr-satellites and gr-leo, used to identify common open-source decoder and
  channel-simulation capabilities; no source is vendored:
  <https://github.com/daniestevez/gr-satellites> and
  <https://github.com/radioconda/gr-leo>.

Normative regression vectors currently frozen in the tests include CRC-16/X-25
for `123456789` (`0x906e`) and the first nine bytes of the CCSDS legacy 255-bit
randomizer (`ff480ec09a0d70bc8e`).

