---
name: write-experiment
description: Invoke before writing experiments.jsonl. Provides the exact JSON structure and required fields for experiment records.
---

# Write Experiment Record

Append one JSON object per line to `/workspace/run/experiments.jsonl`. **Each query gets one line** — not one line per investigation. If an investigation has 5 queries, write 5 records. This is critical for accurate budget tracking (1 record = 1 budget unit).

## Required fields

| Field | Type | Description |
|-------|------|-------------|
| `experiment_id` | string | `base001`, `base002`, ... for base phase; `exp001`, `exp002`, ... for exploration phase |
| `task_id` | string | From task_packet.json |
| `phase` | string | One of: `base`, `exploration` |
| `investigation_id` | string or null | Investigation ID for exploration phase, null for base phase |
| `query_id` | string or null | Query ID within the investigation (e.g. I1-q1), null for base phase |
| `question` | string | Research question being tested |
| `status` | string | One of: `success`, `failed`, `inconclusive` |
| `summary` | string | One-sentence result summary with key numbers |
| `code_path` | string | Relative path, e.g. `code/base001.py` or `code/exp001.py` |
| `artifacts` | array of strings | All output file paths |

## Optional fields

| Field | Type | Description |
|-------|------|-------------|
| `command` | string | Command used to run the code |
| `stdout_summary` | string | Key output lines from stdout |
| `stderr_summary` | string | Error output, empty if none |
| `claim_refs` | array of strings | Claim IDs this experiment supports |
| `limitations` | array of strings | Known limitations of the experiment |

## Field guidance

- `code_path`: relative to `/workspace/run/`, e.g. `code/exp001.py`
- Include failed experiments — they inform the epistemic state
- For exploration phase, `investigation_id` and `query_id` must be set
- For base phase, `investigation_id` and `query_id` must be null

## Writing

Append each record as a single JSON line to `/workspace/run/experiments.jsonl`.
