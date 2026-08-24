"""Preregistered campaign quality gates independent of effect direction."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .audit import audit_campaign
from .campaign import load_records


def _rate(rows: list[dict[str, Any]]) -> float:
    return sum(bool(row["run_success"]) for row in rows) / len(rows)


def evaluate_quality(directory: Path) -> dict[str, Any]:
    """Evaluate frozen integrity, control and informativeness requirements."""
    root = Path(directory)
    manifest = json.loads((root / "campaign.json").read_text())
    rows = load_records(root / "runs.jsonl")
    audit = audit_campaign(root)
    checks: list[dict[str, Any]] = []

    def add(name: str, passed: bool, observed: Any, criterion: str) -> None:
        checks.append(
            {
                "name": name,
                "passed": bool(passed),
                "observed": observed,
                "criterion": criterion,
            }
        )

    add("regenerative_audit", audit["ok"], audit["errors"], "audit.ok is true")
    add(
        "expected_pairs",
        audit["pairs"] == manifest["expected_paired_runs"],
        audit["pairs"],
        f"equals {manifest['expected_paired_runs']}",
    )
    add(
        "expected_records",
        audit["records"] == manifest["expected_policy_records"],
        audit["records"],
        f"equals {manifest['expected_policy_records']}",
    )

    if manifest["profile"] == "controls":
        for policy in ("scripted_manifest_baseline", "bounded_blind_search"):
            positive = [
                row
                for row in rows
                if row["policy"] == policy and row["cell"]["control"] == "positive"
            ]
            negative = [
                row
                for row in rows
                if row["policy"] == policy and row["cell"]["control"] == "negative"
            ]
            positive_rate = _rate(positive)
            negative_rate = _rate(negative)
            add(
                f"positive_control:{policy}",
                positive_rate >= 0.95,
                positive_rate,
                "run-success rate >= 0.95",
            )
            add(
                f"negative_control:{policy}",
                negative_rate <= 0.05,
                negative_rate,
                "run-success rate <= 0.05",
            )

    if manifest["profile"] == "full":
        for policy in ("scripted_manifest_baseline", "bounded_blind_search"):
            primary = [row for row in rows if row["policy"] == policy]
            successes = sum(bool(row["run_success"]) for row in primary)
            add(
                f"nondegenerate:{policy}",
                0 < successes < len(primary),
                {"successes": successes, "runs": len(primary)},
                "at least one success and one failure",
            )

    return {
        "ok": all(check["passed"] for check in checks),
        "profile": manifest["profile"],
        "campaign_manifest_sha256": manifest["manifest_sha256"],
        "checks": checks,
    }
