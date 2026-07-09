# Harness-Opt Artifact Contracts

> **Version:** `1.0` — all artifacts include `"contract_version": "1.0"`.

This directory is the **source of truth** for inter-stage I/O. Python implementations live in [`tools/harness-opt/contracts/models.py`](../../../tools/harness-opt/contracts/models.py) and must stay in sync.

## Principles

1. Stages communicate **only** via files under `reports/<run-name>/`.
2. **Never overwrite** prior runs or reports.
3. Analysis stages (`extract`, `cluster`, `label`) are **trace-only** — no harness code, no `tasks.json`, no `policy.md`.
4. Schema changes require updating JSON schemas here **and** Pydantic models before implementation.

## Artifact index

| File | Schema | Producer | Consumers |
|------|--------|----------|-----------|
| `manifest.json` | [manifest.schema.json](manifest.schema.json) | `generate_report` | All stages, dashboard |
| `features.json` | [features.schema.json](features.schema.json) | `extract_features` | `cluster`, dashboard |
| `clusters_l0.json` | [clusters.schema.json](clusters.schema.json) | `cluster` | dashboard (deterministic mechanism-bucket taxonomy) |
| `clusters.json` | [clusters.schema.json](clusters.schema.json) | `cluster` | `label_clusters`, `build_subset`, dashboard |
| `cluster_labels.json` | [cluster_labels.schema.json](cluster_labels.schema.json) | `label_clusters` | Dashboard, proposal agent |
| `task_summary.csv` | (columns in phase-0 README) | `generate_report` | `build_subset`, dashboard |
| `analysis_summary.md` | (markdown) | `generate_report` | Human, writeup |
| `oracle.json` | [subset_spec.schema.json](subset_spec.schema.json) | `build_subset --mode oracle` | `eval_subset`, dashboard |
| `proposals/<id>/subset_spec.json` | [subset_spec.schema.json](subset_spec.schema.json) | `build_subset --mode cluster` | `eval_subset` |
| `proposals/<id>/subset_results.json` | [subset_results.schema.json](subset_results.schema.json) | `eval_subset` | Dashboard, human |
| `proposals/<id>/metadata.json` | [proposal_metadata.schema.json](proposal_metadata.schema.json) | `propose` (phase 2) | Dashboard, git |

## Directory layout per run

```
reports/<run-name>/
├── manifest.json
├── task_summary.csv
├── features.json
├── clusters_l0.json
├── clusters.json
├── cluster_labels.json
├── analysis_summary.md
├── oracle.json                    # after build-subset --mode oracle
└── proposals/
    └── <proposal-id>/
        ├── metadata.json
        ├── proposal.md
        ├── diff.patch
        ├── subset_spec.json
        ├── subset_results.json
        └── proposal_status.json   # phase 2: accept | reject
```

## Parallel agent rules

See [AGENT_BOUNDARIES.md](AGENT_BOUNDARIES.md).
