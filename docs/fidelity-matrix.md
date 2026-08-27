# Fidelity matrix — 1.0.0

| Domain | Status | Fidelity and limitation |
|---|---|---|
| Mission/OBC | validated in unit/integration tests | deterministic scheduler time, watchdog, reset/session semantics |
| EPS | approximate | energy balance and camera load; no cell/electronics model |
| ADCS/rotor | approximate | angular state, wrap, speed and acceleration; no rigid-body quaternion dynamics |
| Thermal | approximate | first-order sun/eclipse response |
| Storage/payload | behavioral | capacity/accounting and synthetic camera receipts; no optical model |
| Space Packet | byte-vector tested | frozen primary-header subset, not a full PUS implementation |
| Protected TM | lab profile tested | AES-GCM, FECF and replay; not an SDLS conformance claim |
| Orbit | conditional | SGP4 when installed; otherwise labeled two-body fallback |
| Tracking | scenario tested | virtual rotor only; no physical driver |
| Dashboard cyber lab | scenario tested | in-process teaching model; no externally reachable web service |
| AX.25/AFSK | synthetic tested | WAV timing acquisition and FCS; real fixture pending provenance |
| RF/HIL | omitted | intentionally no transmitter, radio device or physical rotor backend |

