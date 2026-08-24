"""Factorial paired campaign runner with immutable provenance."""

from __future__ import annotations

import hashlib
import itertools
import json
import os
import platform
import sys
from collections.abc import Iterable
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np

from . import __version__
from .channel import apply_channel
from .config import Protocol, SimulationConfig
from .modem import modulate_payload
from .policies import (
    BoundedSearchPolicy,
    DirectDecodeAblation,
    ReceiverPolicy,
    ScriptedBaseline,
)
from .safety import safe_output_path
from .seeds import named_rng, rng_pair
from .stats import mcnemar_exact, paired_bootstrap_difference, wilson

ANALYSIS_SEED = 20260824


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def source_sha256() -> str:
    """Hash the installed package's Python source tree in path order."""
    root = Path(__file__).resolve().parent
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*.py")):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def factorial(profile: str) -> list[dict[str, Any]]:
    """Return the preregistered design cells; replications are added separately."""
    if profile == "smoke":
        axes = {
            "protocol": ["AX25_AFSK"],
            "snr_db": [16.0],
            "doppler": [0.0],
            "cfo": [0.0],
            "clock_ppm": [0.0],
            "burst": [False],
            "multipath": [False],
            "phase_inversion": [False],
        }
    elif profile == "quick":
        axes = {
            "protocol": [p.value for p in Protocol],
            "snr_db": [14.0, 5.0],
            "doppler": [0.0, 0.002],
            "cfo": [0.0, 0.004],
            "clock_ppm": [0.0],
            "burst": [False],
            "multipath": [False],
            "phase_inversion": [False],
        }
    elif profile == "controls":
        cells = []
        for protocol in Protocol:
            for control, snr in (("positive", 30.0), ("negative", -20.0)):
                cells.append(
                    {
                        "protocol": protocol.value,
                        "snr_db": snr,
                        "doppler": 0.0,
                        "cfo": 0.0,
                        "clock_ppm": 0.0,
                        "burst": False,
                        "multipath": False,
                        "control": control,
                    }
                )
                cells[-1]["phase_inversion"] = False
        return cells
    elif profile == "stress":
        base = {
            "protocol": Protocol.CCSDS_BPSK.value,
            "snr_db": 16.0,
            "doppler": 0.0,
            "cfo": 0.0,
            "clock_ppm": 0.0,
            "burst": False,
            "multipath": False,
            "phase_inversion": False,
        }
        variations = [
            ("nominal", {}),
            ("cfo", {"cfo": 0.008}),
            ("doppler", {"doppler": 0.005}),
            ("clock", {"clock_ppm": 100.0}),
            ("burst", {"burst": True}),
            ("multipath", {"multipath": True}),
            ("impulse", {"impulse_probability": 0.002}),
            ("phase_inversion", {"phase_inversion": True}),
            ("clipping", {"clip_amplitude": 0.65}),
            ("gain_invariance", {"gain_db": -12.0}),
        ]
        return [dict(base, stress=name, **changes) for name, changes in variations]
    elif profile == "full":
        axes = {
            "protocol": [p.value for p in Protocol],
            "snr_db": [16.0, 10.0, 5.0, 0.0],
            "doppler": [0.0, 0.001, 0.003],
            "cfo": [0.0, 0.004],
            "clock_ppm": [0.0, 50.0],
            "burst": [False, True],
            "multipath": [False, True],
        }
        axes["phase_inversion"] = [False, True]
    else:
        raise ValueError("profile must be smoke, quick, controls, stress, or full")
    names = tuple(axes)
    return [
        dict(zip(names, values))
        for values in itertools.product(*(axes[name] for name in names))
    ]


def config_for_cell(base: SimulationConfig, cell: dict[str, Any]) -> SimulationConfig:
    channel = replace(
        base.channel,
        snr_db=float(cell["snr_db"]),
        doppler_cycles_per_sample=float(cell["doppler"]),
        cfo_cycles_per_sample=float(cell["cfo"]),
        sample_clock_ppm=float(cell["clock_ppm"]),
        burst_erasure_probability=0.02 if cell["burst"] else 0.0,
        burst_length_samples=24 if cell["burst"] else 0,
        multipath_taps=(1 + 0j, 0.25 - 0.1j) if cell["multipath"] else (1 + 0j,),
        multipath_delay_samples=(
            float(cell.get("multipath_delay_samples", 1.5))
            if cell["multipath"]
            else None
        ),
        multipath_gain=(
            float(cell.get("multipath_gain", 0.35)) if cell["multipath"] else 0.0
        ),
        phase_offset_rad=(float(np.pi) if cell.get("phase_inversion", False) else 0.0),
        impulse_probability=float(
            cell.get("impulse_probability", base.channel.impulse_probability)
        ),
        clip_amplitude=cell.get("clip_amplitude", base.channel.clip_amplitude),
        gain_db=float(cell.get("gain_db", base.channel.gain_db)),
    )
    return replace(base, protocol=Protocol(cell["protocol"]), channel=channel)


def _payload(rng: np.random.Generator, length: int, sequence: int) -> bytes:
    prefix = f"SIM:{sequence:04d}:".encode()
    return (
        prefix
        + rng.integers(
            0, 256, size=max(0, length - len(prefix)), dtype=np.uint8
        ).tobytes()
    )


def _policies(include_ablations: bool = False) -> tuple[ReceiverPolicy, ...]:
    primary: tuple[ReceiverPolicy, ...] = (ScriptedBaseline(), BoundedSearchPolicy())
    return primary + ((DirectDecodeAblation(),) if include_ablations else ())


def run_campaign(
    base: SimulationConfig,
    output: Path,
    *,
    profile: str = "quick",
    repetitions: int | None = None,
    frames_per_run: int | None = None,
    save_iq: str = "none",
    include_ablations: bool = False,
) -> dict[str, Any]:
    """Run a paired campaign. Refuses to overwrite any prior campaign directory."""
    output = Path(safe_output_path(output))
    if output.exists():
        raise FileExistsError(f"refusing to overwrite campaign directory: {output}")
    if save_iq not in {"none", "failures", "all"}:
        raise ValueError("save_iq must be none, failures, or all")
    output.mkdir(parents=True)
    (output / "iq").mkdir()
    default_reps = {
        "smoke": 1,
        "quick": 3,
        "controls": 20,
        "stress": 10,
        "full": base.repetitions,
    }
    reps = repetitions if repetitions is not None else default_reps[profile]
    frame_count = (
        frames_per_run
        if frames_per_run is not None
        else (2 if profile == "smoke" else base.frames_per_run)
    )
    cells = factorial(profile)
    policy_names = [policy.name for policy in _policies(include_ablations)]
    design = {
        "design_id": f"{profile}-v1",
        "profile": profile,
        "cells": cells,
        "replications_per_cell": reps,
        "frames_per_run": frame_count,
        "policies": policy_names,
        "master_seed": base.master_seed,
        "primary_estimand": "equally_weighted_marginal_paired_run_success_difference",
        "analysis_version": 1,
        "analysis_seed": ANALYSIS_SEED,
    }
    manifest = {
        "artifact": "cubesec-sim",
        "version": __version__,
        "profile": profile,
        "design_id": design["design_id"],
        "design_sha256": _sha256(_canonical(design)),
        "primary_estimand": design["primary_estimand"],
        "analysis_version": 1,
        "analysis_seed": ANALYSIS_SEED,
        "base_config": base.to_dict(),
        "cells": cells,
        "replications_per_cell": reps,
        "frames_per_run": frame_count,
        "paired": True,
        "save_iq": save_iq,
        "expected_paired_runs": len(cells) * reps,
        "expected_policy_records": len(cells) * reps * len(policy_names),
        "policies": policy_names,
        "include_ablations": include_ablations,
        "source_sha256": source_sha256(),
        "python": sys.version.split()[0],
        "numpy": np.__version__,
        "platform": platform.platform(),
    }
    manifest["manifest_sha256"] = _sha256(_canonical(manifest))
    (output / "campaign.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    records: list[dict[str, Any]] = []
    jsonl = output / "runs.jsonl"
    with jsonl.open("x", encoding="utf-8") as stream:
        for cell_index, cell in enumerate(cells):
            cell_id = _sha256(_canonical(cell))[:16]
            cfg = config_for_cell(base, cell)
            for replication in range(reps):
                channel_rng, _ = rng_pair(base.master_seed, cell_id, replication)
                clean_frames: list[tuple[bytes, np.ndarray]] = []
                impaired_frames: list[np.ndarray] = []
                pass_fractions = [
                    (sequence + 0.5) / frame_count for sequence in range(frame_count)
                ]
                for sequence in range(frame_count):
                    expected = _payload(channel_rng, cfg.payload_bytes, sequence)
                    clean = modulate_payload(expected, cfg, sequence)
                    impaired = apply_channel(
                        clean,
                        cfg.channel,
                        channel_rng,
                        pass_fraction=pass_fractions[sequence],
                    )
                    clean_frames.append((expected, clean))
                    impaired_frames.append(impaired)
                iq_bytes = b"".join(
                    frame.astype("<c8", copy=False).tobytes()
                    for frame in impaired_frames
                )
                iq_hash = _sha256(iq_bytes)
                pair_id = f"{cell_index:04d}-{replication:04d}-{cell_id}"
                pair_records = []
                for policy in _policies(include_ablations):
                    policy_rng = named_rng(
                        base.master_seed, cell_id, replication, policy.name
                    )
                    outcomes = []
                    call_count = 0
                    errors: dict[str, int] = {}
                    for frame_index, ((expected, _), impaired) in enumerate(
                        zip(clean_frames, impaired_frames)
                    ):
                        result = policy.decode(
                            impaired.copy(),
                            cfg,
                            policy_rng,
                            pass_fraction=pass_fractions[frame_index],
                        )
                        correct = result.success and result.payload == expected
                        outcomes.append(correct)
                        call_count += len(result.calls)
                        if not correct:
                            key = result.error or "payload_mismatch"
                            errors[key] = errors.get(key, 0) + 1
                    record = {
                        "pair_id": pair_id,
                        "cell_id": cell_id,
                        "cell": cell,
                        "replication": replication,
                        "policy": policy.name,
                        "frames": frame_count,
                        "correct_frames": sum(outcomes),
                        "run_success": all(outcomes),
                        "tool_calls": call_count,
                        "errors": errors,
                        "iq_sha256": iq_hash,
                        "config_sha256": _sha256(_canonical(cfg.to_dict())),
                        "master_seed": base.master_seed,
                        "frame_samples": [len(x) for x in impaired_frames],
                        "frame_pass_fractions": pass_fractions,
                        "frame_times_s": [
                            fraction * cfg.pass_seconds for fraction in pass_fractions
                        ],
                        "policy_seed_label": policy.name,
                    }
                    pair_records.append(record)
                save = save_iq == "all" or (
                    save_iq == "failures"
                    and any(not x["run_success"] for x in pair_records)
                )
                if save:
                    iq_path = output / "iq" / f"{pair_id}.c64"
                    with iq_path.open("xb") as iq_stream:
                        iq_stream.write(iq_bytes)
                    for record in pair_records:
                        record["iq_path"] = str(iq_path.relative_to(output))
                for record in pair_records:
                    stream.write(json.dumps(record, sort_keys=True) + "\n")
                    stream.flush()
                    os.fsync(stream.fileno())
                    records.append(record)
    summary = summarize(records, manifest)
    summary["runs_sha256"] = _sha256(jsonl.read_bytes())
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n"
    )
    return summary


def load_records(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def summarize(
    records: Iterable[dict[str, Any]], manifest: dict[str, Any] | None = None
) -> dict[str, Any]:
    rows = list(records)
    by_policy: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_policy.setdefault(row["policy"], []).append(row)
    policy_summary: dict[str, Any] = {}
    failure_summary: dict[str, dict[str, int]] = {}
    for name, group in by_policy.items():
        successes = sum(bool(x["run_success"]) for x in group)
        interval = wilson(successes, len(group))
        policy_summary[name] = {
            "successes": successes,
            "runs": len(group),
            "rate": successes / len(group),
            "wilson_95": list(interval),
            "correct_frames": sum(x["correct_frames"] for x in group),
            "frames": sum(x["frames"] for x in group),
            "tool_calls": sum(x["tool_calls"] for x in group),
        }
        errors: dict[str, int] = {}
        for row in group:
            for error, count in row.get("errors", {}).items():
                errors[error] = errors.get(error, 0) + int(count)
        failure_summary[name] = errors
    baseline = {
        x["pair_id"]: bool(x["run_success"])
        for x in by_policy.get("scripted_manifest_baseline", [])
    }
    candidate = {
        x["pair_id"]: bool(x["run_success"])
        for x in by_policy.get("bounded_blind_search", [])
    }
    common = sorted(set(baseline) & set(candidate))
    comparison: dict[str, Any] = {}
    if common:
        b = [baseline[key] for key in common]
        c = [candidate[key] for key in common]
        comparison = mcnemar_exact(b, c)
        comparison["paired_bootstrap"] = paired_bootstrap_difference(
            [float(x) for x in b],
            [float(x) for x in c],
            seed=(ANALYSIS_SEED if manifest is None else manifest["analysis_seed"]),
        )
    factors: dict[str, Any] = {}
    if rows:
        for factor in rows[0].get("cell", {}):
            levels: dict[str, Any] = {}
            for level in sorted({str(row["cell"][factor]) for row in rows}):
                levels[level] = {}
                for policy, group in by_policy.items():
                    subset = [row for row in group if str(row["cell"][factor]) == level]
                    success = sum(bool(row["run_success"]) for row in subset)
                    levels[level][policy] = {
                        "successes": success,
                        "runs": len(subset),
                        "rate": success / len(subset),
                        "wilson_95": list(wilson(success, len(subset))),
                    }
            factors[factor] = levels
    return {
        "policy": policy_summary,
        "failures": failure_summary,
        "factors_descriptive": factors,
        "paired_comparison": comparison,
        "record_count": len(rows),
        "pair_count": len(common),
        "manifest_sha256": None
        if manifest is None
        else manifest.get("manifest_sha256"),
    }
