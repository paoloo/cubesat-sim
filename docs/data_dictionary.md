# Data dictionary

## `campaign.json`

- `manifest_sha256`: hash of the canonical manifest before this field is added.
- `source_sha256`: hash of all installed `cubesec_sim/*.py` files in path order.
- `design_sha256`: hash of cells, denominators, policies, master seed, estimand
  and analysis version.
- `cells`: complete frozen factorial cells.
- `replications_per_cell`, `frames_per_run`: exact denominators.
- `base_config`: safe synthetic configuration used to derive each cell.
- `expected_paired_runs`, `expected_policy_records`: completeness gates.

## `runs.jsonl`

Each line is one policy result nested in one paired channel realization.

- `pair_id`: deterministic cell/replication identifier.
- `cell`, `cell_id`, `replication`: design coordinates.
- `policy`, `policy_seed_label`: policy identity and order-independent RNG label.
- `frames`, `correct_frames`, `run_success`: primary and secondary outcomes.
- `frame_pass_fractions`, `frame_times_s`, `frame_samples`: frame index within
  the synthetic pass.
- `tool_calls`, `errors`: trajectory counts; error events are not independent
  experimental units.
- `iq_sha256`, `config_sha256`: provenance links.
- `iq_path`: present only when IQ preservation was requested.

## `summary.json`

- `policy`: aggregate numerators, denominators, rates and Wilson intervals.
- `paired_comparison`: exact McNemar counts and paired bootstrap interval.
- `factors_descriptive`: descriptive strata; no implicit per-cell testing.
- `failures`: nested event counts by policy.
- `runs_sha256`: hash of the exact JSONL summarized.

## `report/`

`policy_results.csv`, `factor_results.csv`, `cell_results.csv`,
`failure_events.csv`, `report.md` and `policy_table.tex` are derived outputs. `report_manifest.json` binds them to
the campaign manifest and records a SHA-256 for every report file.
