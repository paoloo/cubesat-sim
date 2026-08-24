"""Command-line interface using only the standard library."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .audit import audit_campaign
from .campaign import load_records, run_campaign, summarize
from .config import SimulationConfig
from .quality import evaluate_quality
from .report import export_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cubesec-sim", description="Offline synthetic CubeSat simulation"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init-config", help="write a safe synthetic configuration")
    init.add_argument("path", type=Path)
    run = sub.add_parser("run", help="run a preregistered paired campaign")
    run.add_argument("--config", type=Path)
    run.add_argument("--output", type=Path, required=True)
    run.add_argument(
        "--profile",
        choices=("smoke", "quick", "controls", "stress", "full"),
        default="quick",
    )
    run.add_argument("--repetitions", type=int)
    run.add_argument("--frames", type=int)
    run.add_argument("--save-iq", choices=("none", "failures", "all"), default="none")
    run.add_argument(
        "--ablations", action="store_true", help="include the direct-decode ablation"
    )
    analyze = sub.add_parser("analyze", help="recompute a summary from JSONL")
    analyze.add_argument("runs", type=Path)
    audit = sub.add_parser("audit", help="regenerate IQ and verify campaign hashes")
    audit.add_argument("directory", type=Path)
    report = sub.add_parser(
        "report", help="export Markdown, CSV and LaTeX result tables"
    )
    report.add_argument("directory", type=Path)
    quality = sub.add_parser(
        "quality", help="apply preregistered integrity and control gates"
    )
    quality.add_argument("directory", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "init-config":
        with args.path.open("x", encoding="utf-8") as stream:
            stream.write(SimulationConfig().to_json() + "\n")
        return 0
    if args.command == "run":
        cfg = (
            SimulationConfig()
            if args.config is None
            else SimulationConfig.from_dict(json.loads(args.config.read_text()))
        )
        result = run_campaign(
            cfg,
            args.output,
            profile=args.profile,
            repetitions=args.repetitions,
            frames_per_run=args.frames,
            save_iq=args.save_iq,
            include_ablations=args.ablations,
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    if args.command == "analyze":
        print(json.dumps(summarize(load_records(args.runs)), indent=2, sort_keys=True))
        return 0
    if args.command == "audit":
        result = audit_campaign(args.directory)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["ok"] else 2
    if args.command == "quality":
        result = evaluate_quality(args.directory)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["ok"] else 3
    print(json.dumps(export_report(args.directory), indent=2, sort_keys=True))
    return 0
