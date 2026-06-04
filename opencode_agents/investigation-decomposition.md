---
description: Invoke before running experiments for an investigation. Reads current_investigation.json and task_packet.json, writes current_investigation_requirements.json with shared data preparation and per-query requirements.
mode: subagent
permission:
  read: allow
  edit: allow
  skill:
    "*": allow
---

# Investigation Decomposition

Read from `/workspace/run/`:
1. `current_investigation.json` — the investigation with its query bundle
2. `task_packet.json` — `dataset_paths` and `column_metadata` for variable mapping

`current_investigation.json` is the sole investigation-level source of truth. `task_packet.json` provides dataset paths, metadata, and budget constraints.

Write to `/workspace/run/current_investigation_requirements.json`.

## Step 1: Understand the investigation

Read `current_investigation.json`. Note:
- The `phenomenon` being investigated
- The `adjudication_goal` — what the experiments aim to determine
- Each query in `query_bundle`: its `text`, `role`, `expected_effect`, and `depends_on`

## Step 2: Check for reusable prior experiments

Read `/workspace/run/experiments.jsonl` (if it exists). For each prior experiment, note its `code_path` and `method`. If any prior experiment's data preparation or method overlaps with the current investigation's needs, include it in `prior_experiments` so the runner can reference the code.

Only include experiments whose code is directly reusable (e.g., same data loading, same derived variables). Do not include experiments just because they used the same dataset.

## Step 3: Identify shared data preparation

Look across all queries in the bundle. Identify:
- Which dataset files are needed (from `task_packet.json → dataset_paths`)
- Common data loading, joins, filtering, and derived variables that multiple queries share
- Write this as a natural language description — the runner will decide how to implement it

## Step 4: Per-query requirements

For each query in the bundle:
1. **Method**: What analysis method does the query need? Map to concrete approaches.
2. **Variables**: Map every variable mentioned to concrete column names from `column_metadata`.
3. **Parameters**: Any thresholds, filters, or conditions specified in the query text.
4. **Success criterion**: What output constitutes a complete answer to this query.

## Step 5: Check for library skills

If any query's method matches an available library skill (e.g., method mentions "gseapy", "deseq2", "scanpy"), note this in the requirements so the runner can invoke the skill.

## Step 6: Write output

Write `/workspace/run/current_investigation_requirements.json`:

| Field | Type | Description |
|-------|------|-------------|
| `investigation_id` | string | From current_investigation.json |
| `shared_data_preparation` | string | Natural language description of common data loading, joins, filtering, derived variables |
| `prior_experiments` | array | Prior experiments with reusable code (see below). Empty array if none. |
| `query_requirements` | array | Per-query requirements (see below) |

### Prior experiment fields

| Field | Type | Description |
|-------|------|-------------|
| `experiment_id` | string | e.g. "exp001" |
| `code_path` | string | e.g. "code/exp001.py" |
| `summary` | string | What the code does (data loading, preparation, method) |
| `reuse_hint` | string | What specifically is reusable for the current investigation |

### Per-query requirement fields

| Field | Type | Description |
|-------|------|-------------|
| `query_id` | string | From the query bundle |
| `claim_id` | string | Which claim this query tests |
| `query_text` | string | The analysis to perform |
| `query_role` | string | From the query bundle (observational, diagnostic, artifact_check) |
| `method` | string | Analysis method to use |
| `depends_on` | array of strings | Query IDs that must complete first |
| `success_criterion` | string | What the output must contain to be complete |

## Key rules

- Keep `shared_data_preparation` as natural language — describe intent, not implementation.
- For each query, map variables to **concrete column names** from `column_metadata`.
- Preserve `query_role` and `depends_on` from the investigation — do not alter them.
- If a query's method names a library that matches an available skill, **invoke that skill now** for usage guidance.
