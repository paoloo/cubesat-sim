"""Evidence-producing integrated verification runner."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
from typing import Any

import numpy as np

from .. import __version__
from .core import Context, EventBus, VirtualClock, WallClock
from .scenarios import AFSKScenario, SCENARIOS
from .spacecraft import Spacecraft


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime): return value.isoformat()
    if isinstance(value, set): return sorted(value)
    if isinstance(value, bytes): return value.hex()
    raise TypeError(f"not JSON serializable: {type(value).__name__}")


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, default=_json_default) + "\n", encoding="utf-8")


def _source_hash() -> str:
    digest = hashlib.sha256(); root = Path(__file__).parents[1]
    for path in sorted(root.rglob("*.py")):
        digest.update(path.relative_to(root).as_posix().encode()); digest.update(path.read_bytes())
    return digest.hexdigest()


def verify(output: Path, *, suite: str = "all", seed: int = 20260826, wall_clock: bool = False, afsk_wav: Path | None = None, afsk_capture: Path | None = None) -> dict[str, Any]:
    if output.exists(): raise FileExistsError(f"refusing to overwrite {output}")
    output.mkdir(parents=True); scenarios_dir = output / "scenarios"; scenarios_dir.mkdir()
    names = list(SCENARIOS) if suite == "all" else [suite]
    unknown = set(names)-set(SCENARIOS)
    if unknown: raise ValueError(f"unknown scenarios: {sorted(unknown)}")
    clock = WallClock() if wall_clock else VirtualClock()
    run_id = hashlib.sha256(f"SIMUL-v1:{seed}:{','.join(names)}".encode()).hexdigest()[:16]
    bus = EventBus(clock); spacecraft = Spacecraft(clock, bus, run_id, seed); ctx = Context(run_id, seed, clock, bus, spacecraft)
    results = []
    for name in names:
        scenario = AFSKScenario(afsk_capture or afsk_wav) if name == "afsk" else SCENARIOS[name]()
        event_start = len(bus.events)
        try: result = scenario.execute(ctx)
        except Exception as exc:
            from .core import ScenarioResult
            result = ScenarioResult(scenario.scenario_id, False, {}, {}, {}, f"{type(exc).__name__}: {exc}")
        target = scenarios_dir / result.scenario_id; target.mkdir()
        evidence_dir = target / "evidence"; evidence_dir.mkdir()
        _write_json(target / "result.json", asdict(result))
        _write_json(evidence_dir / "evidence.json", result.evidence)
        with (target / "transcript.jsonl").open("w", encoding="utf-8") as stream:
            for event in bus.events[event_start:]: stream.write(json.dumps(asdict(event), sort_keys=True, default=_json_default)+"\n")
        results.append(result)
    manifest = {"schema": 1, "run_id": run_id, "version": __version__, "evolved_from": {"version": "0.2.0", "commit": "fffbc40953baafd2f20497b350aa000b8047ba47"}, "seed": seed, "clock": "wall" if wall_clock else "virtual", "source_sha256": _source_hash(), "suite": names, "offline_only": True, "afsk_fixture": str(afsk_capture or afsk_wav) if (afsk_capture or afsk_wav) else "synthetic"}
    environment = {"python": platform.python_version(), "platform": platform.platform(), "numpy": np.__version__, "pid": os.getpid()}
    summary = {"run_id": run_id, "passed": all(result.passed for result in results), "scenarios_passed": sum(result.passed for result in results), "scenarios_total": len(results), "results": [{"id": r.scenario_id, "passed": r.passed, "error": r.error} for r in results], "final_spacecraft_state": spacecraft.telemetry()}
    _write_json(output/"manifest.json", manifest); _write_json(output/"environment.json", environment); _write_json(output/"summary.json", summary)
    with (output/"events.jsonl").open("w", encoding="utf-8") as stream:
        for event in bus.records(): stream.write(json.dumps(event, sort_keys=True, default=_json_default)+"\n")
    lines = ["# CubeSec-Sim integrated verification", "", f"Run: `{run_id}`", f"Result: **{'PASS' if summary['passed'] else 'FAIL'}**", "", "| Scenario | Result |", "|---|---|"]
    lines.extend(f"| {r.scenario_id} | {'PASS' if r.passed else 'FAIL'} |" for r in results)
    (output/"report.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    return summary
