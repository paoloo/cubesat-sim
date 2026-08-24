"""Regenerative audit of a completed campaign."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .campaign import (
    _canonical,
    _payload,
    _policies,
    _sha256,
    config_for_cell,
    load_records,
    source_sha256,
    summarize,
)
from .channel import apply_channel
from .config import SimulationConfig
from .modem import modulate_payload
from .seeds import rng_pair


def audit_campaign(directory: Path) -> dict[str, Any]:
    directory = Path(directory)
    manifest = json.loads((directory / "campaign.json").read_text())
    records = load_records(directory / "runs.jsonl")
    errors: list[str] = []
    stored_manifest_hash = manifest.get("manifest_sha256")
    unhashed = dict(manifest)
    unhashed.pop("manifest_sha256", None)
    if _sha256(_canonical(unhashed)) != stored_manifest_hash:
        errors.append("manifest_sha256_mismatch")
    if manifest.get("source_sha256") != source_sha256():
        errors.append("source_sha256_mismatch")
    design = {
        "design_id": manifest.get("design_id"),
        "profile": manifest.get("profile"),
        "cells": manifest.get("cells"),
        "replications_per_cell": manifest.get("replications_per_cell"),
        "frames_per_run": manifest.get("frames_per_run"),
        "policies": manifest.get("policies"),
        "master_seed": manifest.get("base_config", {}).get("master_seed"),
        "primary_estimand": manifest.get("primary_estimand"),
        "analysis_version": manifest.get("analysis_version"),
        "analysis_seed": manifest.get("analysis_seed"),
    }
    if _sha256(_canonical(design)) != manifest.get("design_sha256"):
        errors.append("design_sha256_mismatch")
    if len(records) != manifest.get("expected_policy_records"):
        errors.append("record_count_mismatch")
    stored_summary = json.loads((directory / "summary.json").read_text())
    expected_summary = summarize(records, manifest)
    expected_summary["runs_sha256"] = hashlib.sha256(
        (directory / "runs.jsonl").read_bytes()
    ).hexdigest()
    if _canonical(stored_summary) != _canonical(expected_summary):
        errors.append("summary_mismatch")
    base = SimulationConfig.from_dict(manifest["base_config"])
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in records:
        groups.setdefault(row["pair_id"], []).append(row)
    regenerated = 0
    for pair_id, rows in groups.items():
        first = rows[0]
        expected_policies = {
            policy.name for policy in _policies(bool(manifest.get("include_ablations")))
        }
        if {row.get("policy") for row in rows} != expected_policies:
            errors.append(f"{pair_id}:policy_set_mismatch")
        if any(row.get("policy_seed_label") != row.get("policy") for row in rows):
            errors.append(f"{pair_id}:policy_seed_label_mismatch")
        if len({row["iq_sha256"] for row in rows}) != 1:
            errors.append(f"{pair_id}:policy_iq_hash_mismatch")
        if len({row["config_sha256"] for row in rows}) != 1:
            errors.append(f"{pair_id}:policy_config_hash_mismatch")
        if any(row.get("master_seed") != base.master_seed for row in rows):
            errors.append(f"{pair_id}:master_seed_mismatch")
        cfg = config_for_cell(base, first["cell"])
        channel_rng, _ = rng_pair(
            base.master_seed, first["cell_id"], int(first["replication"])
        )
        frames = []
        sizes = []
        fractions = [
            (sequence + 0.5) / int(first["frames"])
            for sequence in range(int(first["frames"]))
        ]
        for sequence in range(int(first["frames"])):
            payload = _payload(channel_rng, cfg.payload_bytes, sequence)
            clean = modulate_payload(payload, cfg, sequence)
            impaired = apply_channel(
                clean, cfg.channel, channel_rng, pass_fraction=fractions[sequence]
            ).astype("<c8", copy=False)
            frames.append(impaired.tobytes())
            sizes.append(len(impaired))
        regenerated_hash = hashlib.sha256(b"".join(frames)).hexdigest()
        if regenerated_hash != first["iq_sha256"]:
            errors.append(f"{pair_id}:regenerated_iq_hash_mismatch")
        if sizes != first.get("frame_samples"):
            errors.append(f"{pair_id}:frame_index_mismatch")
        if fractions != first.get("frame_pass_fractions"):
            errors.append(f"{pair_id}:pass_fraction_mismatch")
        expected_times = [fraction * cfg.pass_seconds for fraction in fractions]
        if expected_times != first.get("frame_times_s"):
            errors.append(f"{pair_id}:frame_time_mismatch")
        iq_path = first.get("iq_path")
        if iq_path:
            stored = directory / iq_path
            if (
                not stored.is_file()
                or hashlib.sha256(stored.read_bytes()).hexdigest() != first["iq_sha256"]
            ):
                errors.append(f"{pair_id}:stored_iq_hash_mismatch")
        regenerated += 1
    expected_pairs = manifest.get("expected_paired_runs")
    if len(groups) != expected_pairs:
        errors.append("pair_count_mismatch")
    report_dir = directory / "report"
    if report_dir.exists():
        report_manifest_path = report_dir / "report_manifest.json"
        if not report_manifest_path.is_file():
            errors.append("report_manifest_missing")
        else:
            report_manifest = json.loads(report_manifest_path.read_text())
            if report_manifest.get("campaign_manifest_sha256") != stored_manifest_hash:
                errors.append("report_campaign_hash_mismatch")
            for name, expected_hash in report_manifest.get("files", {}).items():
                path = report_dir / name
                if (
                    not path.is_file()
                    or hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash
                ):
                    errors.append(f"report:{name}:hash_mismatch")
    return {
        "ok": not errors,
        "errors": errors,
        "records": len(records),
        "pairs": len(groups),
        "regenerated_pairs": regenerated,
        "manifest_sha256": stored_manifest_hash,
    }
