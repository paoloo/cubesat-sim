"""Publication-oriented Markdown, CSV and LaTeX exports."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _tex(value: str) -> str:
    return value.replace("_", "\\_").replace("%", "\\%").replace("&", "\\&")


def export_report(campaign_directory: Path) -> dict[str, Any]:
    root = Path(campaign_directory)
    manifest = json.loads((root / "campaign.json").read_text())
    summary = json.loads((root / "summary.json").read_text())
    records = [
        json.loads(line)
        for line in (root / "runs.jsonl").read_text().splitlines()
        if line.strip()
    ]
    report_dir = root / "report"
    report_dir.mkdir()
    policy_rows = []
    for policy, row in sorted(summary["policy"].items()):
        policy_rows.append(
            {
                "policy": policy,
                "successes": row["successes"],
                "runs": row["runs"],
                "run_success_rate": row["rate"],
                "wilson_low": row["wilson_95"][0],
                "wilson_high": row["wilson_95"][1],
                "correct_frames": row["correct_frames"],
                "frames": row["frames"],
                "frame_correct_rate": row["correct_frames"] / row["frames"],
                "tool_calls": row["tool_calls"],
            }
        )
    _write_csv(report_dir / "policy_results.csv", list(policy_rows[0]), policy_rows)
    factor_rows = []
    for factor, levels in sorted(summary["factors_descriptive"].items()):
        for level, policies in sorted(levels.items()):
            for policy, row in sorted(policies.items()):
                factor_rows.append(
                    {
                        "factor": factor,
                        "level": level,
                        "policy": policy,
                        "successes": row["successes"],
                        "runs": row["runs"],
                        "rate": row["rate"],
                        "wilson_low": row["wilson_95"][0],
                        "wilson_high": row["wilson_95"][1],
                    }
                )
    _write_csv(report_dir / "factor_results.csv", list(factor_rows[0]), factor_rows)
    factor_names = sorted({name for row in records for name in row["cell"]})
    cell_groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    cell_values: dict[str, dict[str, Any]] = {}
    for row in records:
        cell_key = json.dumps(row["cell"], sort_keys=True, separators=(",", ":"))
        cell_values[cell_key] = row["cell"]
        cell_groups.setdefault((cell_key, row["policy"]), []).append(row)
    cell_rows = []
    for (cell_key, policy), group in sorted(cell_groups.items()):
        successes = sum(bool(row["run_success"]) for row in group)
        row = {name: cell_values[cell_key].get(name, "") for name in factor_names}
        row.update(
            {
                "policy": policy,
                "successes": successes,
                "runs": len(group),
                "rate": successes / len(group),
                "correct_frames": sum(item["correct_frames"] for item in group),
                "frames": sum(item["frames"] for item in group),
            }
        )
        cell_rows.append(row)
    _write_csv(
        report_dir / "cell_results.csv",
        factor_names
        + ["policy", "successes", "runs", "rate", "correct_frames", "frames"],
        cell_rows,
    )
    failure_rows = []
    for policy, failures in sorted(summary["failures"].items()):
        for failure, count in sorted(
            failures.items(), key=lambda item: (-item[1], item[0])
        ):
            failure_rows.append({"policy": policy, "failure": failure, "events": count})
    if failure_rows:
        _write_csv(
            report_dir / "failure_events.csv", list(failure_rows[0]), failure_rows
        )
    comparison = summary["paired_comparison"]
    lines = [
        "# CubeSec-Sim campaign report",
        "",
        f"- Profile: `{manifest['profile']}`",
        f"- Manifest SHA-256: `{manifest['manifest_sha256']}`",
        f"- Design SHA-256: `{manifest['design_sha256']}`",
        f"- Source SHA-256: `{manifest['source_sha256']}`",
        f"- Paired runs: {summary['pair_count']}",
        f"- Policy records: {summary['record_count']}",
        "",
        "## Primary policy results",
        "",
        "| Policy | Successful runs | Rate | Wilson 95% | Correct frames |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in policy_rows:
        lines.append(
            f"| `{row['policy']}` | {row['successes']}/{row['runs']} | {row['run_success_rate']:.4f} "
            f"| [{row['wilson_low']:.4f}, {row['wilson_high']:.4f}] "
            f"| {row['correct_frames']}/{row['frames']} |"
        )
    lines.extend(
        [
            "",
            "## Paired primary comparison",
            "",
            f"- Baseline-only successes: {comparison.get('baseline_only', 0)}",
            f"- Candidate-only successes: {comparison.get('candidate_only', 0)}",
            f"- Exact McNemar p-value: {comparison.get('p_exact', 1.0):.6g}",
        ]
    )
    bootstrap = comparison.get("paired_bootstrap", {})
    if bootstrap:
        lines.append(
            f"- Paired mean difference: {bootstrap['mean_difference']:.4f} "
            f"(95% bootstrap [{bootstrap['ci_low']:.4f}, {bootstrap['ci_high']:.4f}])"
        )
    lines.extend(
        ["", "Factor strata are descriptive; failure events are nested in runs.", ""]
    )
    (report_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")
    tex_lines = [
        "% Generated by cubesec-sim; do not edit manually.",
        "\\begin{tabular}{lrrrr}",
        "\\hline",
        "Política & Sucessos & Ensaios & Taxa & Quadros corretos \\\\",
        "\\hline",
    ]
    for row in policy_rows:
        tex_lines.append(
            f"{_tex(row['policy'])} & {row['successes']} & {row['runs']} & "
            f"{row['run_success_rate']:.3f} & {row['correct_frames']}/{row['frames']} \\\\"
        )
    tex_lines.extend(["\\hline", "\\end{tabular}", ""])
    (report_dir / "policy_table.tex").write_text("\n".join(tex_lines), encoding="utf-8")
    files = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(report_dir.iterdir())
    }
    report_manifest = {
        "campaign_manifest_sha256": manifest["manifest_sha256"],
        "files": files,
    }
    (report_dir / "report_manifest.json").write_text(
        json.dumps(report_manifest, indent=2, sort_keys=True) + "\n"
    )
    return report_manifest
