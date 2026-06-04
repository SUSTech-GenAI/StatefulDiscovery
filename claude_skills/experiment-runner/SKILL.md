---
name: experiment-runner
description: Invoke after investigation-decomposition. Runs all queries in an investigation bundle using shared data preparation. Writes code and results.
context: fork
allowed-tools: Read, Write, Bash, Glob, Skill
---

# Experiment Runner

You execute an investigation's query bundle in a clean context. Your job: implement shared data preparation, then run each query's analysis, following `current_investigation_requirements.json` strictly.

## Step 1: Read inputs

Read from `/workspace/run/`:
1. `current_investigation_requirements.json` — shared data preparation and per-query requirements
2. `task_packet.json` — `dataset_paths` and `column_metadata`

**Do NOT read** `epistemic_state.json`, `patterns.json`, `investigations.json`, or any other state files. You work from requirements and raw data only.

## Step 2: Check prior experiments for reusable code

If `current_investigation_requirements.json` has a `prior_experiments` array, read each referenced `code_path`. Look for reusable data loading, preparation, or utility code. You may copy and adapt code from prior experiments — this avoids redoing work already done in earlier investigations.

Only reuse **code** (data loading, transformations, utility functions). Do not reuse **conclusions** or **result interpretations**.

## Step 3: Inspect data and plan preparation

Read the first few rows of each raw data file to understand column names, data types, and structure.

Use the `shared_data_preparation` description from requirements to plan:
- Which files to load
- How to join tables
- What derived variables to compute
- Common filtering or aggregation

If prior experiments have reusable code, start from that. Otherwise build from scratch.

Verify the plan against actual data. If the shared preparation description doesn't match the actual data structure, adapt the implementation but keep the same intent.

## Step 4: Determine experiment numbers

Count lines in `/workspace/run/experiments.jsonl` (0 if file doesn't exist). Number experiments sequentially from there: `exp{N+1:03d}`, `exp{N+2:03d}`, etc. — one experiment ID per query in the bundle.

## Step 5: Respect query ordering

Check `depends_on` for each query. Execute queries in an order that satisfies dependencies:
- Queries with empty `depends_on` can run first
- Queries that depend on others must run after their dependencies complete

## Step 6: Write and run code

Before writing code, check if any query's method matches an available library skill. If so, invoke it for usage guidance.

For each query in the bundle:
1. Write code to `/workspace/run/code/exp{NNN}.py`
2. The code must:
   - Load raw data files from `task_packet.json → dataset_paths`
   - Implement shared data preparation (can reuse code/imports across queries)
   - Run the exact method specified in the query requirements
   - Print key results clearly: the answer, key statistics, sample size
   - Save results to `/workspace/run/code/exp{NNN}_results.json`
3. Run with `python3`. If it errors, diagnose, fix, and retry (max 2 retries per query).

You may write all queries in a single script or separate scripts — use your judgment based on how much code they share. If using a single script, still produce separate `_results.json` files per query.

## Step 7: Report

After execution, print a summary for each query:

```
query_id: I1-q1
experiment_id: exp001
code_path: code/exp001.py
status: success | failed
sample_size: <N>
method: <from requirements>
result: <key answer matching success_criterion>
key_stats: <main statistics>
```

## Step 8: Self-check

After all queries complete, review results:

1. **Cross-query consistency**: Do results across queries make sense together? Does the diagnostic query's result align with the observational query?
2. **Data preparation**: Is the shared preparation correct? Sample sizes consistent?
3. **Output verification**: Read experiment outputs and verify numbers match expectations.

If you find a problem in a specific query, fix and rerun as a new experiment. Report both the original and corrected version.

## Key rules

- **Strict execution**: follow `current_investigation_requirements.json` exactly.
- **No unauthorized operations**: do not add filters, subsets, or analyses not in the requirements.
- **Self-correct data issues**, but do not second-guess the requirements themselves.
- **Report all queries**: even if some fail, report results for those that succeed.
- **Check skills before workarounds**: if you hit a technical obstacle (e.g., ID format mismatch, unfamiliar file format, missing library), check available skills first — do not assume a tool is unavailable without looking.
