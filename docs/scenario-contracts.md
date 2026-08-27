# Integrated scenario contracts

All scenarios run offline against mission `SIM-CUBE-01`. Inputs that identify a
real transmitter, RF device, network service or spacecraft are outside scope.

| ID | Input | Success oracle | Shared effect |
|---|---|---|---|
| 01 visibility | synthetic TLE, UTC interval, station, mask | ordered AOS/TCA/LOS and elevation above mask | common orbit geometry |
| 02 space-packet | APID, sequence and JSON transaction | frozen header bytes and correlated telemetry | COMMS frame count |
| 03 stateful | session and modular counter | sync, flag grant, replay rejection | persistent COMMS session |
| 04 protected-TM | packet, SPI and counters | GCM, FECF and anti-replay checks | spacecraft security association |
| 05 tracking | pass geometry and rotor limits | finite samples and bounded RMS/maximum error | common orbit geometry |
| 06 dashboard | synthetic viewer claim and camera target | exploit only vulnerable profile; patch denies it | EPS, ADCS, storage and camera |
| 07 AFSK | passive mono PCM WAV or synthetic fixture | timing recovery and valid AX.25 FCS | receive-only COMMS evidence |

Each result contains boolean checks, metrics, evidence and an error field. The
runner catches scenario exceptions and records them as failures rather than
silently aborting the rest of the laboratory.

